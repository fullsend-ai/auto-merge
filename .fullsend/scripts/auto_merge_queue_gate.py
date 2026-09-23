#!/usr/bin/env python3
"""Fail-closed authorization for GitHub's queue-generated merge revision."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from auto_merge_finalize import TRUSTED_RECEIPT_AUTHORS, idempotency_key, parse_receipt_header


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
QUEUE_REF_RE = re.compile(r"^refs/heads/gh-readonly-queue/(?P<base>[^/]+)/pr-(?P<number>[1-9][0-9]*)-[^/]+$")
RISK_LEVELS = {"low", "moderate", "elevated", "high", "critical"}


class QueueGateError(RuntimeError):
    """Queue evidence is incomplete, stale, or unauthorized."""


def gh_json(*args: str) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=45,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gh error"
        raise QueueGateError(f"GitHub query failed: {detail[:500]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise QueueGateError("GitHub query returned invalid JSON") from exc


def active_merge_queue_required(rulesets: list[dict[str, Any]]) -> bool:
    return any(
        ruleset.get("enforcement") == "active"
        and any(rule.get("type") == "merge_queue" for rule in ruleset.get("rules", []))
        for ruleset in rulesets
    )


def evaluate_merge_group(
    event: dict[str, Any],
    pull_request: dict[str, Any],
    comments: list[dict[str, Any]],
    rulesets: list[dict[str, Any]],
    repository: str,
    allowed_risk_levels: set[str],
) -> dict[str, Any]:
    failures: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            failures.append(reason)

    group = event.get("merge_group") or {}
    head_sha = str(group.get("head_sha") or "")
    base_sha = str(group.get("base_sha") or "")
    head_ref = str(group.get("head_ref") or "")
    match = QUEUE_REF_RE.fullmatch(head_ref)
    number = int(match.group("number")) if match else 0
    base_ref = match.group("base") if match else ""

    require(event.get("action") == "checks_requested", "event action is not checks_requested")
    require((event.get("repository") or {}).get("full_name") == repository, "repository mismatch")
    require(SHA_RE.fullmatch(head_sha) is not None, "queue head SHA is invalid")
    require(SHA_RE.fullmatch(base_sha) is not None, "queue base SHA is invalid")
    require(match is not None, "queue head ref does not identify one pull request")
    require(active_merge_queue_required(rulesets), "an active merge-queue rule was not found")
    require(pull_request.get("number") == number, "pull request number does not match queue ref")
    require(pull_request.get("state") == "open", "pull request is not open")
    require(pull_request.get("draft") is False, "pull request is a draft")
    require((pull_request.get("base") or {}).get("ref") == base_ref, "pull request base does not match queue ref")
    require((pull_request.get("head") or {}).get("repo", {}).get("full_name") == repository, "fork pull requests are not allowed")

    labels = [str(label.get("name") or "") for label in pull_request.get("labels", [])]
    risk_labels = [label for label in labels if label.startswith("risk/")]
    risk_level = risk_labels[0].removeprefix("risk/") if len(risk_labels) == 1 else ""
    require(len(risk_labels) == 1 and risk_level in RISK_LEVELS, "exactly one valid risk assessment is required")
    require(risk_level in allowed_risk_levels, f"risk level {risk_level or '<missing>'} is not allowed")

    pr_head_sha = str((pull_request.get("head") or {}).get("sha") or "")
    trusted_queued_receipt = False
    for comment in comments:
        author = str((comment.get("user") or {}).get("login") or "")
        if author not in TRUSTED_RECEIPT_AUTHORS:
            continue
        receipt = parse_receipt_header(str(comment.get("body") or ""))
        expected_key = ""
        if receipt is not None:
            expected_key = idempotency_key(
                {
                    "repository": repository,
                    "pull_request_number": number,
                    "head_sha": receipt["head"],
                    "base_ref": receipt["base_ref"],
                    "base_sha": receipt["base_sha"],
                    "policy_fingerprint": receipt["policy"],
                },
                "queue",
            )
        if (
            receipt is not None
            and receipt["phase"] == "queued"
            and receipt["decision"] == "APPROVE"
            and receipt["marker_key"] == expected_key
            and receipt["head"] == pr_head_sha
            and receipt["base_ref"] == base_ref
            and receipt["base_sha"] == base_sha
        ):
            trusted_queued_receipt = True
            break
    require(trusted_queued_receipt, "no trusted queue receipt binds the PR head to this queue base")

    return {
        "authorized": not failures,
        "failures": failures,
        "pull_request_number": number,
        "pull_request_head_sha": pr_head_sha,
        "queue_head_sha": head_sha,
        "queue_base_sha": base_sha,
        "risk_level": risk_level,
    }


def main() -> int:
    repository = os.environ.get("AUTO_MERGE_ALLOWED_REPOSITORY", "")
    allowed_risk_levels = {item.strip() for item in os.environ.get("AUTO_MERGE_ALLOWED_RISK_LEVELS", "").split(",") if item.strip()}
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    if not repository or not allowed_risk_levels or not event_path.is_file():
        raise QueueGateError("trusted queue policy or event input is missing")
    event = json.loads(event_path.read_text(encoding="utf-8"))
    head_ref = str((event.get("merge_group") or {}).get("head_ref") or "")
    match = QUEUE_REF_RE.fullmatch(head_ref)
    if match is None:
        raise QueueGateError("queue head ref does not identify one pull request")
    number = int(match.group("number"))

    pull_request = gh_json("api", f"repos/{repository}/pulls/{number}")
    comments = gh_json("api", f"repos/{repository}/issues/{number}/comments?per_page=100")
    summaries = gh_json("api", f"repos/{repository}/rulesets?includes_parents=true")
    rulesets = [gh_json("api", f"repos/{repository}/rulesets/{item['id']}") for item in summaries if item.get("id") is not None]
    result = evaluate_merge_group(event, pull_request, comments, rulesets, repository, allowed_risk_levels)
    if not result["authorized"]:
        raise QueueGateError("; ".join(result["failures"]))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QueueGateError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"auto-merge queue authorization failed closed: {exc}", file=sys.stderr)
        raise SystemExit(1)
