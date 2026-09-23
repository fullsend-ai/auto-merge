#!/usr/bin/env python3
"""Revalidate only Fullsend semantic authority on GitHub's merge-group revision."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from auto_merge_finalize import SCM_OPERATION, TRUSTED_RECEIPT_AUTHORS, idempotency_key, parse_receipt_header
from auto_merge_gate import SHA_RE, build_evidence, collect_snapshot, csv_values, read_quality


QUEUE_REF_RE = re.compile(r"^refs/heads/gh-readonly-queue/(?P<base>[^/]+)/pr-(?P<number>[1-9][0-9]*)-[^/]+$")


class QueueGateError(RuntimeError):
    """Queue semantic evidence is incomplete, stale, or unauthorized."""


def evaluate_merge_group(
    event: dict[str, Any],
    snapshot: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            failures.append(reason)

    repository = policy["repository"]
    group = event.get("merge_group") or {}
    queue_head_sha = str(group.get("head_sha") or "")
    queue_base_sha = str(group.get("base_sha") or "")
    head_ref = str(group.get("head_ref") or "")
    match = QUEUE_REF_RE.fullmatch(head_ref)
    number = int(match.group("number")) if match else 0
    base_ref = match.group("base") if match else ""
    pr = snapshot["pull_request"]
    pr_head_sha = str((pr.get("head") or {}).get("sha") or "")

    require(event.get("action") == "checks_requested", "event action is not checks_requested")
    require((event.get("repository") or {}).get("full_name") == repository, "repository mismatch")
    require(SHA_RE.fullmatch(queue_head_sha) is not None, "queue head SHA is invalid")
    require(SHA_RE.fullmatch(queue_base_sha) is not None, "queue base SHA is invalid")
    require(match is not None, "queue head ref does not identify one pull request")
    require(pr.get("number") == number, "pull request number does not match queue ref")
    require((pr.get("base") or {}).get("ref") == base_ref, "pull request base does not match queue ref")
    require((pr.get("head") or {}).get("repo", {}).get("full_name") == repository, "fork pull request is outside this lab's security scope")

    current = build_evidence(snapshot, policy)
    require(current.get("prerequisites", {}).get("ready_for_semantic_evaluation") is True, "current semantic prerequisites are not satisfied")

    trusted_receipt = False
    for comment in snapshot["comments"]:
        author = str((comment.get("user") or {}).get("login") or "")
        if author not in TRUSTED_RECEIPT_AUTHORS:
            continue
        receipt = parse_receipt_header(str(comment.get("body") or ""))
        if receipt is None:
            continue
        receipt_binding = {
            "repository": repository,
            "pull_request_number": number,
            "head_sha": receipt["head"],
            "base_ref": receipt["base_ref"],
            "base_sha": receipt["base_sha"],
            "policy_fingerprint": receipt["policy"],
            "semantic_fingerprint": receipt["semantic"],
        }
        expected_key = idempotency_key(receipt_binding, SCM_OPERATION)
        if (
            receipt["phase"] == "submitted"
            and receipt["decision"] == "AUTHORIZE"
            and receipt["key"] == expected_key
            and receipt["marker_key"] == expected_key
            and receipt["head"] == pr_head_sha
            and receipt["base_ref"] == base_ref
            and receipt["base_sha"] == queue_base_sha
            and receipt["policy"] == current["binding"]["policy_fingerprint"]
            and receipt["semantic"] == current["binding"]["semantic_fingerprint"]
        ):
            trusted_receipt = True
            break
    require(trusted_receipt, "no trusted authorization receipt matches the current semantic context and queue base")

    return {
        "authorized": not failures,
        "failures": failures,
        "scm_policy_checked": False,
        "pull_request_number": number,
        "pull_request_head_sha": pr_head_sha,
        "queue_head_sha": queue_head_sha,
        "queue_base_sha": queue_base_sha,
        "semantic_fingerprint": current["binding"]["semantic_fingerprint"],
    }


def policy_from_env() -> dict[str, Any]:
    try:
        return {
            "repository": os.environ["AUTO_MERGE_ALLOWED_REPOSITORY"],
            "base_ref": os.environ.get("AUTO_MERGE_BASE_REF", "main"),
            "policy_version": os.environ["AUTO_MERGE_POLICY_VERSION"],
            "mode": os.environ.get("AUTO_MERGE_MODE", "lab-automatic"),
            "semantic_reviewer": os.environ["AUTO_MERGE_SEMANTIC_REVIEWER"],
            "risk_assessment_producer": os.environ["AUTO_MERGE_RISK_ASSESSMENT_PRODUCER"],
            "artifact_correlation_minutes": int(os.environ.get("AUTO_MERGE_ARTIFACT_CORRELATION_MINUTES", "1")),
            "maximum_unattended_risk": os.environ.get("AUTO_MERGE_MAXIMUM_UNATTENDED_RISK", "moderate"),
            "human_signal_associations": sorted(csv_values(os.environ.get("AUTO_MERGE_HUMAN_SIGNAL_ASSOCIATIONS", "OWNER,MEMBER,COLLABORATOR"))),
            "review_quality_mode": os.environ.get("AUTO_MERGE_REVIEW_QUALITY_MODE", "off"),
            "review_quality_minimum_score": float(os.environ.get("AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SCORE", "0.98")),
            "review_quality_minimum_samples": int(os.environ.get("AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SAMPLES", "50")),
            "custom_instructions": os.environ.get("AUTO_MERGE_CUSTOM_INSTRUCTIONS", ""),
        }
    except (KeyError, ValueError) as exc:
        raise QueueGateError("trusted semantic policy is missing or malformed") from exc


def main() -> int:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    if not event_path.is_file():
        raise QueueGateError("merge-group event input is missing")
    event = json.loads(event_path.read_text(encoding="utf-8"))
    head_ref = str((event.get("merge_group") or {}).get("head_ref") or "")
    match = QUEUE_REF_RE.fullmatch(head_ref)
    if match is None:
        raise QueueGateError("queue head ref does not identify one pull request")
    policy = policy_from_env()
    quality = read_quality(os.environ.get("AUTO_MERGE_REVIEW_QUALITY_FILE", ""))
    snapshot = collect_snapshot(policy["repository"], int(match.group("number")), quality)
    result = evaluate_merge_group(event, snapshot, policy)
    if not result["authorized"]:
        raise QueueGateError("; ".join(result["failures"]))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QueueGateError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"auto-merge semantic queue authorization failed closed: {exc}", file=sys.stderr)
        raise SystemExit(1)
