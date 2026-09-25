#!/usr/bin/env python3
"""Collect semantic Auto-Merge evidence without reimplementing SCM policy."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import quote


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_URL_RE = re.compile(
    r"^https://github\.com/(?P<repo>[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)/"
    r"pull/(?P<number>[1-9][0-9]*)$"
)
RISK_RE = re.compile(
    r"\*\*Risk Assessment:\s*(?P<level>low|moderate|elevated|high|critical)\s*"
    r"\((?P<score>[1-5])/5\)\*\*",
    re.IGNORECASE,
)
RISK_MARKER = "<!-- fullsend:risk-assessment -->"
REVIEW_MARKER = "<!-- fullsend:review-agent -->"
REVIEW_HEAD_RE = re.compile(r"<!-- \*\*Head SHA:\*\* (?P<head>[0-9a-f]{40}) -->")
CONTROL_PREFIXES = ("/fs-",)
IGNORED_MARKERS = (
    "<!-- fullsend:agent-status:",
    "<!-- fullsend:auto-merge-receipt:",
    "<!-- fullsend:risk-assessment -->",
    "<!-- fullsend:review-agent -->",
)
MAX_COMMENT_CHARS = 4_000
MAX_CHANGED_FILES = 100
MAX_TRACE_REFS = 50
MAX_LINKED_ISSUES = 20
MAX_ISSUE_BODY_CHARS = 8_000
MAX_TRUSTED_HUMAN_SIGNALS = 100
MAX_UNTRUSTED_HUMAN_SIGNALS = 20
QUALITY_MODES = {"off", "observe", "enforce"}
RISK_LEVELS = {"low": 1, "moderate": 2, "elevated": 3, "high": 4, "critical": 5}


class GateError(RuntimeError):
    """A forge lookup or evidence-integrity failure."""


def canonical_hash(document: dict[str, Any]) -> str:
    unsigned = json.loads(json.dumps(document))
    unsigned.pop("context_fingerprint", None)
    if isinstance(unsigned.get("binding"), dict):
        unsigned["binding"].pop("context_fingerprint", None)
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def stable_hash(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def policy_fingerprint(policy: dict[str, Any]) -> str:
    return stable_hash(policy)


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_time(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc)


def gh_json(*args: str) -> Any:
    env = os.environ.copy()
    if not env.get("GH_TOKEN"):
        raise GateError("GH_TOKEN is not set")
    proc = subprocess.run(
        ["gh", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=45,
    )
    if proc.returncode != 0:
        message = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gh error"
        raise GateError(f"GitHub query failed: {message[:500]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GateError("GitHub query returned invalid JSON") from exc


def gh_pages(endpoint: str) -> list[dict[str, Any]]:
    pages = gh_json("api", "--paginate", "--slurp", endpoint)
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise GateError(f"GitHub query returned malformed pagination data for {endpoint}")
    return [item for page in pages for item in page if isinstance(item, dict)]


def change_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    files = snapshot.get("files") or []
    if not isinstance(files, list):
        raise GateError("pull-request files response is malformed")
    bounded: list[dict[str, Any]] = []
    for item in files[:MAX_CHANGED_FILES]:
        if not isinstance(item, dict) or not item.get("filename"):
            continue
        bounded.append(
            {
                "filename": str(item.get("filename"))[:500],
                "status": str(item.get("status") or "unknown")[:32],
                "additions": int(item.get("additions") or 0),
                "deletions": int(item.get("deletions") or 0),
                "changes": int(item.get("changes") or 0),
            }
        )
    return {
        "files": bounded,
        "total_files": len(files),
        "truncated": len(files) > MAX_CHANGED_FILES,
        "additions": sum(int(item.get("additions") or 0) for item in files if isinstance(item, dict)),
        "deletions": sum(int(item.get("deletions") or 0) for item in files if isinstance(item, dict)),
    }


def trace_references(path: str) -> list[dict[str, str]]:
    if not path:
        return []
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("trace references file is missing or invalid JSON") from exc
    refs = raw.get("refs") if isinstance(raw, dict) else raw
    if not isinstance(refs, list):
        raise GateError("trace references must be a JSON array or an object with refs")
    bounded: list[dict[str, str]] = []
    for item in refs[:MAX_TRACE_REFS]:
        if not isinstance(item, dict):
            raise GateError("trace reference is not an object")
        bounded.append(
            {
                key: str(item.get(key) or "")[:500]
                for key in ("agent", "run_id", "trace_id", "purpose", "url")
                if item.get(key) is not None
            }
        )
    return bounded


def linked_issue_context(repository: str, pull_number: int) -> list[dict[str, Any]]:
    """Resolve same-repository issues explicitly linked to a pull request."""
    timeline = gh_pages(f"repos/{repository}/issues/{pull_number}/timeline?per_page=100")
    references: dict[int, str] = {}
    for event in timeline:
        if str(event.get("event") or "") not in {"cross-referenced", "connected"}:
            continue
        source = event.get("source") or {}
        issue = source.get("issue") if isinstance(source, dict) else None
        if not isinstance(issue, dict):
            continue
        try:
            number = int(issue.get("number") or 0)
        except (TypeError, ValueError):
            continue
        if number <= 0 or number == pull_number:
            continue
        issue_repository = str((issue.get("repository") or {}).get("full_name") or "")
        if issue_repository != repository:
            continue
        references[number] = str(event.get("event") or "cross-referenced")

    linked: list[dict[str, Any]] = []
    for number, relationship in sorted(references.items())[:MAX_LINKED_ISSUES]:
        issue = gh_json("api", f"repos/{repository}/issues/{number}")
        try:
            issue_number = int(issue.get("number") or 0) if isinstance(issue, dict) else 0
        except (TypeError, ValueError):
            issue_number = 0
        if not isinstance(issue, dict) or issue_number != number:
            raise GateError("GitHub returned malformed linked-issue data")
        labels = issue.get("labels") or []
        if not isinstance(labels, list):
            raise GateError("GitHub returned malformed linked-issue labels")
        linked.append(
            {
                "source": "github_linked_issue",
                "relationship": relationship,
                "repository": repository,
                "number": number,
                "url": str(issue.get("html_url") or "")[:500],
                "title": str(issue.get("title") or "")[:500],
                "statement": str(issue.get("body") or "")[:MAX_ISSUE_BODY_CHARS],
                "state": str(issue.get("state") or "")[:32],
                "author": str((issue.get("user") or {}).get("login") or "")[:200],
                "labels": [str((label or {}).get("name") or "")[:100] for label in labels[:50] if isinstance(label, dict)],
            }
        )
    return linked


def collect_snapshot(repository: str, number: int, quality: dict[str, Any] | None = None) -> dict[str, Any]:
    pr_before = gh_json("api", f"repos/{repository}/pulls/{number}")
    head_sha = str((pr_before.get("head") or {}).get("sha") or "")
    base_ref = str((pr_before.get("base") or {}).get("ref") or "")
    if not SHA_RE.fullmatch(head_sha) or not base_ref:
        raise GateError("pull request returned an invalid head SHA or base ref")
    branch_endpoint = f"repos/{repository}/branches/{quote(base_ref, safe='')}"
    base_before = gh_json("api", branch_endpoint)

    comments = gh_pages(f"repos/{repository}/issues/{number}/comments?per_page=100")
    reviews = gh_pages(f"repos/{repository}/pulls/{number}/reviews?per_page=100")
    files_before = gh_pages(f"repos/{repository}/pulls/{number}/files?per_page=100")
    linked_issues_before = linked_issue_context(repository, number)

    pr_after = gh_json("api", f"repos/{repository}/pulls/{number}")
    base_after = gh_json("api", branch_endpoint)
    files_after = gh_pages(f"repos/{repository}/pulls/{number}/files?per_page=100")
    linked_issues_after = linked_issue_context(repository, number)
    if (pr_after.get("head") or {}).get("sha") != head_sha:
        raise GateError("pull-request head changed while semantic evidence was collected")
    if (pr_after.get("base") or {}).get("ref") != base_ref:
        raise GateError("pull-request base ref changed while semantic evidence was collected")
    if (base_before.get("commit") or {}).get("sha") != (base_after.get("commit") or {}).get("sha"):
        raise GateError("base branch changed while semantic evidence was collected")
    if files_before != files_after:
        raise GateError("pull-request files changed while semantic evidence was collected")
    if linked_issues_before != linked_issues_after:
        raise GateError("linked issues changed while semantic evidence was collected")

    return {
        "pull_request": pr_after,
        "base_branch": base_after,
        "comments": comments,
        "reviews": reviews,
        "files": files_after,
        "linked_issues": linked_issues_after,
        "review_quality": quality or {},
    }


def _latest_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        state = str(review.get("state") or "").upper()
        if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        login = str((review.get("user") or {}).get("login") or "")
        if not login:
            continue
        prior = latest.get(login)
        key = (str(review.get("submitted_at") or ""), int(review.get("id") or 0))
        prior_key = (str((prior or {}).get("submitted_at") or ""), int((prior or {}).get("id") or 0))
        if prior is None or key > prior_key:
            latest[login] = review
    return list(latest.values())


def review_attestation(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    head_sha = str((snapshot["pull_request"].get("head") or {}).get("sha") or "")
    provider = str(policy.get("semantic_provider") or "fullsend-review-agent").casefold()
    attestation_file = str(policy.get("review_attestation_file") or "")
    if attestation_file:
        try:
            raw = json.loads(Path(attestation_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GateError("configured semantic review attestation is unreadable or invalid") from exc
        if not isinstance(raw, dict):
            raise GateError("configured semantic review attestation must be a JSON object")
        file_provider = str(raw.get("provider") or "").casefold()
        file_head = str(raw.get("head_sha") or "")
        decision = str(raw.get("decision") or "").upper()
        reviewer = str(raw.get("reviewer") or "")
        submitted_at = str(raw.get("submitted_at") or "")
        summary = str(raw.get("summary") or "")[:MAX_COMMENT_CHARS]
        if file_provider != provider or decision != "APPROVE" or file_head != head_sha:
            return {
                "authority": provider,
                "decision": "MISSING",
                "provider": file_provider or provider,
                "reviewer": reviewer,
                "head_sha": file_head,
                "review_id": str(raw.get("review_id") or ""),
                "run_id": str(raw.get("run_id") or ""),
                "submitted_at": submitted_at,
                "summary": summary,
                "source": "trusted_attestation_file",
            }
        if not reviewer or not submitted_at or not summary or parse_time(submitted_at) is None:
            raise GateError("configured semantic review attestation is incomplete")
        return {
            "authority": provider,
            "decision": "APPROVE",
            "provider": provider,
            "reviewer": reviewer,
            "head_sha": head_sha,
            "review_id": str(raw.get("review_id") or ""),
            "run_id": str(raw.get("run_id") or ""),
            "submitted_at": submitted_at,
            "summary": summary,
            "source": "trusted_attestation_file",
        }

    reviewer = str(policy["semantic_reviewer"]).casefold()
    matches = [
        review
        for review in _latest_reviews(snapshot["reviews"])
        if str((review.get("user") or {}).get("login") or "").casefold() == reviewer
        and str(review.get("state") or "").upper() == "APPROVED"
        and review.get("commit_id") == head_sha
    ]
    if not matches:
        return {
            "authority": provider,
            "decision": "MISSING",
            "provider": provider,
            "reviewer": reviewer,
            "head_sha": "",
            "review_id": 0,
            "submitted_at": "",
        }
    match = max(matches, key=lambda item: (str(item.get("submitted_at") or ""), int(item.get("id") or 0)))
    return {
        "authority": provider,
        "decision": "APPROVE",
        "provider": provider,
        "reviewer": reviewer,
        "head_sha": head_sha,
        "review_id": int(match.get("id") or 0),
        "submitted_at": str(match.get("submitted_at") or ""),
    }


def review_summary(snapshot: dict[str, Any], policy: dict[str, Any], attestation: dict[str, Any]) -> dict[str, Any]:
    if attestation.get("source") == "trusted_attestation_file":
        current = attestation.get("decision") == "APPROVE" and parse_time(str(attestation.get("submitted_at") or "")) is not None
        return {
            "status": "CURRENT" if current else "MISSING",
            "head_sha": str(attestation.get("head_sha") or ""),
            "comment_id": 0,
            "updated_at": str(attestation.get("submitted_at") or ""),
            "correlation_seconds": 0 if current else None,
            "summary": str(attestation.get("summary") or "")[:MAX_COMMENT_CHARS],
            "source": "trusted_attestation_file",
        }
    producer = str(policy["semantic_reviewer"]).casefold()
    expected_head = str(attestation.get("head_sha") or "")
    candidates: list[tuple[dict[str, Any], re.Match[str]]] = []
    for comment in snapshot["comments"]:
        body = str(comment.get("body") or "")
        author = str((comment.get("user") or {}).get("login") or "").casefold()
        head_match = REVIEW_HEAD_RE.search(body)
        if author == producer and REVIEW_MARKER in body and head_match is not None:
            candidates.append((comment, head_match))
    matching = [item for item in candidates if item[1].group("head") == expected_head]
    if not matching:
        return {"status": "MISSING", "head_sha": "", "comment_id": 0, "updated_at": "", "summary": ""}
    comment, match = max(
        matching,
        key=lambda item: (str(item[0].get("updated_at") or item[0].get("created_at") or ""), int(item[0].get("id") or 0)),
    )
    summary_time = parse_time(str(comment.get("updated_at") or comment.get("created_at") or ""))
    review_time = parse_time(str(attestation.get("submitted_at") or ""))
    correlation_seconds = (review_time - summary_time).total_seconds() if summary_time and review_time else None
    current = correlation_seconds is not None and 0 <= correlation_seconds <= int(policy["artifact_correlation_minutes"]) * 60
    review_text = REVIEW_HEAD_RE.sub("", str(comment.get("body") or ""), count=1)
    review_text = review_text.replace(REVIEW_MARKER, "", 1).strip()[:MAX_COMMENT_CHARS]
    return {
        "status": "CURRENT" if current else "UNBOUND",
        "head_sha": match.group("head"),
        "comment_id": int(comment.get("id") or 0),
        "updated_at": str(comment.get("updated_at") or comment.get("created_at") or ""),
        "correlation_seconds": int(correlation_seconds) if correlation_seconds is not None else None,
        "summary": review_text,
    }


def risk_assessment(
    snapshot: dict[str, Any],
    policy: dict[str, Any],
    attestation: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    producer = str(policy["risk_assessment_producer"]).casefold()
    candidates: list[tuple[dict[str, Any], re.Match[str]]] = []
    for comment in snapshot["comments"]:
        body = str(comment.get("body") or "")
        author = str((comment.get("user") or {}).get("login") or "").casefold()
        match = RISK_RE.search(body)
        if author == producer and RISK_MARKER in body and match is not None:
            candidates.append((comment, match))
    if not candidates:
        return {
            "authority": "fullsend-risk-assessment",
            "producer": producer,
            "status": "MISSING",
            "head_sha": "",
            "level": "",
            "score": 0,
            "comment_id": 0,
            "updated_at": "",
            "summary": "",
        }
    comment, match = max(
        candidates,
        key=lambda item: (str(item[0].get("updated_at") or item[0].get("created_at") or ""), int(item[0].get("id") or 0)),
    )
    risk_time = parse_time(str(comment.get("updated_at") or comment.get("created_at") or ""))
    summary_time = parse_time(str(summary.get("updated_at") or ""))
    correlation_seconds = (summary_time - risk_time).total_seconds() if risk_time and summary_time else None
    correlated = (
        attestation.get("decision") == "APPROVE"
        and summary.get("status") == "CURRENT"
        and summary.get("head_sha") == attestation.get("head_sha")
        and correlation_seconds is not None
        and 0 <= correlation_seconds <= int(policy["artifact_correlation_minutes"]) * 60
    )
    body = str(comment.get("body") or "")
    return {
        "authority": "fullsend-risk-assessment",
        "producer": producer,
        "status": "CURRENT" if correlated else "UNBOUND",
        "head_sha": attestation.get("head_sha", "") if correlated else "",
        "level": match.group("level").lower(),
        "score": int(match.group("score")),
        "comment_id": int(comment.get("id") or 0),
        "updated_at": str(comment.get("updated_at") or comment.get("created_at") or ""),
        "correlated_review_id": int(attestation.get("review_id") or 0),
        "correlated_review_summary_comment_id": int(summary.get("comment_id") or 0),
        "correlation_seconds": int(correlation_seconds) if correlation_seconds is not None else None,
        "summary": body[:MAX_COMMENT_CHARS],
    }


def _is_human(user: dict[str, Any]) -> bool:
    login = str(user.get("login") or "")
    return bool(login) and str(user.get("type") or "User").casefold() != "bot" and not login.endswith("[bot]")


def _human_signal(item: dict[str, Any], channel: str) -> dict[str, Any] | None:
    user = item.get("user") or {}
    body = str(item.get("body") or "").strip()
    if not _is_human(user) or not body or body.startswith(CONTROL_PREFIXES) or any(marker in body for marker in IGNORED_MARKERS):
        return None
    return {
        "channel": channel,
        "id": int(item.get("id") or 0),
        "author": str(user.get("login") or ""),
        "author_association": str(item.get("author_association") or "NONE").upper(),
        "created_at": str(item.get("created_at") or item.get("submitted_at") or ""),
        "updated_at": str(item.get("updated_at") or item.get("submitted_at") or item.get("created_at") or ""),
        "body": body[:MAX_COMMENT_CHARS],
    }


def human_context(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    allowed = {item.upper() for item in policy["human_signal_associations"]}
    pr_author = str((snapshot["pull_request"].get("user") or {}).get("login") or "").casefold()
    signals: list[dict[str, Any]] = []
    for item in snapshot["comments"]:
        signal = _human_signal(item, "conversation")
        if signal is None:
            continue
        trusted_actor = signal["author_association"] in allowed or signal["author"].casefold() == pr_author
        signal["trusted_actor"] = trusted_actor
        signals.append(signal)
    signals.sort(key=lambda item: (item["updated_at"], item["channel"], item["id"]))
    trusted = [signal for signal in signals if signal["trusted_actor"]]
    untrusted = [signal for signal in signals if not signal["trusted_actor"]]
    retained = trusted[-MAX_TRUSTED_HUMAN_SIGNALS:] + untrusted[-MAX_UNTRUSTED_HUMAN_SIGNALS:]
    retained.sort(key=lambda item: (item["updated_at"], item["channel"], item["id"]))
    return {
        "signals": retained,
        "trusted_total": len(trusted),
        "untrusted_total": len(untrusted),
        "trusted_truncated": len(trusted) > MAX_TRUSTED_HUMAN_SIGNALS,
        "untrusted_truncated": len(untrusted) > MAX_UNTRUSTED_HUMAN_SIGNALS,
    }


def normalize_quality(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {"status": "UNAVAILABLE"}
    try:
        score = float(raw["score"])
        sample_count = int(raw["sample_count"])
    except (KeyError, TypeError, ValueError):
        return {"status": "MALFORMED"}
    if not 0 <= score <= 1 or sample_count < 0:
        return {"status": "MALFORMED"}
    return {
        "status": "AVAILABLE",
        "metric": str(raw.get("metric") or "review_correctly_approved"),
        "score": score,
        "sample_count": sample_count,
        "measured_at": str(raw.get("measured_at") or ""),
        "scope": str(raw.get("scope") or ""),
        "reviewer_version": str(raw.get("reviewer_version") or ""),
        "judge_version": str(raw.get("judge_version") or ""),
    }


def semantic_context(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    attestation = review_attestation(snapshot, policy)
    summary = review_summary(snapshot, policy, attestation)
    humans = human_context(snapshot, policy)
    return {
        "linked_issues": snapshot.get("linked_issues") or [],
        "review_attestation": attestation,
        "review_summary": summary,
        "risk_assessment": risk_assessment(snapshot, policy, attestation, summary),
        "human_signals": humans["signals"],
        "human_signal_integrity": {key: value for key, value in humans.items() if key != "signals"},
        "review_quality": normalize_quality(snapshot.get("review_quality") or {}),
        "repository_policy": {
            "maximum_unattended_risk": policy["maximum_unattended_risk"],
            "custom_instructions": policy["custom_instructions"],
            "review_quality_mode": policy["review_quality_mode"],
            "review_quality_minimum_score": policy["review_quality_minimum_score"],
            "review_quality_minimum_samples": policy["review_quality_minimum_samples"],
        },
    }


def evaluate_snapshot(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pr = snapshot["pull_request"]
    repository = policy["repository"]
    head_sha = str((pr.get("head") or {}).get("sha") or "")
    live_base_sha = str((snapshot.get("base_branch") or {}).get("commit", {}).get("sha") or "")
    context = semantic_context(snapshot, policy)
    failures: list[str] = []
    checks: list[dict[str, str]] = []

    def require(check_id: str, label: str, condition: bool, reason: str, detail: str | None = None) -> None:
        checks.append(
            {
                "id": check_id,
                "label": label,
                "status": "pass" if condition else "fail",
                "detail": (detail if condition and detail else ("passed" if condition else reason)),
            }
        )
        if not condition:
            failures.append(reason)

    require("mode", "Auto-Merge mode is supported", policy.get("mode") in {"observe", "lab-automatic"}, "POC mode is unsupported")
    require("review_quality_mode", "Review-quality mode is supported", policy.get("review_quality_mode") in QUALITY_MODES, "review quality mode is unsupported")
    require("pr_open", "Pull request is open and not a draft", pr.get("state") == "open" and pr.get("draft") is False, "pull request is not open or is a draft")
    require("head_sha", "Pull-request head SHA is valid", SHA_RE.fullmatch(head_sha) is not None, "head SHA is invalid")
    require("base_sha", "Live base SHA is valid", SHA_RE.fullmatch(live_base_sha) is not None, "live base SHA is invalid")
    require("base_ref", "Base branch is in the configured scope", (pr.get("base") or {}).get("ref") == policy["base_ref"], "base ref is outside the configured scope")
    require("base_repository", "Base repository is the configured repository", (pr.get("base") or {}).get("repo", {}).get("full_name") == repository, "base repository mismatch")
    require("head_repository", "Pull request is not from a fork", (pr.get("head") or {}).get("repo", {}).get("full_name") == repository, "fork pull requests are outside this lab's security scope")
    authority_label = "Review Agent" if context["review_attestation"].get("authority") == "fullsend-review-agent" else "configured semantic reviewer"
    require("review_attestation", f"Exact-head {authority_label} attestation is current", context["review_attestation"]["decision"] == "APPROVE", f"exact-head {authority_label} attestation is missing or stale")
    require("review_summary", "Exact-head review summary is current", context["review_summary"]["status"] == "CURRENT", "exact-head Review summary is missing or stale")
    require("risk_assessment", "Exact-head risk assessment is current", context["risk_assessment"]["status"] == "CURRENT", "exact-head risk assessment is missing or cannot be bound to the Review run")
    require("human_context_bound", "Trusted human context is within the evidence bound", not context["human_signal_integrity"]["trusted_truncated"], "trusted human context exceeds the safe evidence bound")
    risk_level = context["risk_assessment"].get("level")
    maximum_risk = policy.get("maximum_unattended_risk")
    require("risk_policy", "Maximum unattended-risk policy is valid", maximum_risk in RISK_LEVELS, "maximum unattended risk policy is invalid")
    if context["risk_assessment"]["status"] == "CURRENT" and maximum_risk in RISK_LEVELS:
        require(
            "risk_ceiling",
            "Risk is within the unattended-merge policy",
            risk_level in RISK_LEVELS and RISK_LEVELS[risk_level] <= RISK_LEVELS[maximum_risk],
            f"risk assessment {risk_level or 'unknown'} exceeds unattended policy {maximum_risk}",
        )
    else:
        require(
            "risk_ceiling",
            "Risk is within the unattended-merge policy",
            True,
            "risk ceiling could not be evaluated",
            "not applicable until the risk assessment is current and the policy is valid",
        )
        checks[-1]["status"] = "not_applicable"

    quality = context["review_quality"]
    if policy["review_quality_mode"] == "enforce":
        require("review_quality_available", "Required review-quality evidence is available", quality.get("status") == "AVAILABLE", "required Review quality evidence is unavailable")
        if quality.get("status") == "AVAILABLE":
            require("review_quality_samples", "Review-quality sample count meets policy", quality["sample_count"] >= policy["review_quality_minimum_samples"], "Review quality evidence has too few samples")
            require("review_quality_score", "Review-quality score meets policy", quality["score"] >= policy["review_quality_minimum_score"], "Review quality score is below repository policy")
        else:
            require(
                "review_quality_samples",
                "Review-quality sample count meets policy",
                True,
                "review quality sample count could not be evaluated",
                "not applicable until valid review-quality evidence is available",
            )
            checks[-1]["status"] = "not_applicable"
            require(
                "review_quality_score",
                "Review-quality score meets policy",
                True,
                "review quality score could not be evaluated",
                "not applicable until valid review-quality evidence is available",
            )
            checks[-1]["status"] = "not_applicable"
    else:
        require(
            "review_quality_policy",
            "Optional review-quality policy is not blocking",
            True,
            "review quality policy is blocking",
            f"not enforced (mode: {policy['review_quality_mode']})",
        )

    return {
        "ready_for_semantic_evaluation": not failures,
        "failures": failures,
        "checks": checks,
        "scm_policy_checked": False,
        "note": "SCM owns checks, review counts, conversations, mergeability, branch freshness, and queue policy.",
        "semantic_context": context,
    }


def semantic_fingerprint(binding_seed: dict[str, Any], context: dict[str, Any], policy: dict[str, Any]) -> str:
    return stable_hash(
        {
            "repository": binding_seed["repository"],
            "pull_request_number": binding_seed["pull_request_number"],
            "head_sha": binding_seed["head_sha"],
            "base_ref": binding_seed["base_ref"],
            "base_sha": binding_seed["base_sha"],
            "policy_fingerprint": policy_fingerprint(policy),
            "semantic_context": context,
        }
    )


def build_evidence(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pr = snapshot["pull_request"]
    evaluation = evaluate_snapshot(snapshot, policy)
    binding_seed = {
        "repository": policy["repository"],
        "pull_request_number": int(pr["number"]),
        "head_sha": str((pr.get("head") or {}).get("sha") or ""),
        "base_ref": str((pr.get("base") or {}).get("ref") or ""),
        "base_sha": str((snapshot.get("base_branch") or {}).get("commit", {}).get("sha") or ""),
    }
    document: dict[str, Any] = {
        "schema_version": "2",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "binding": {
            **binding_seed,
            "policy_fingerprint": policy_fingerprint(policy),
            "semantic_fingerprint": semantic_fingerprint(binding_seed, evaluation["semantic_context"], policy),
        },
        "pull_request": {
            "url": str(pr.get("html_url") or ""),
            "title": str(pr.get("title") or "")[:500],
            "body": str(pr.get("body") or "")[:8_000],
            "author": str((pr.get("user") or {}).get("login") or ""),
        },
        "intent": {
            "source": "pull_request",
            "statement": str(pr.get("body") or "")[:8_000],
            "title": str(pr.get("title") or "")[:500],
        },
        "linked_issues": snapshot.get("linked_issues") or [],
        "change_context": change_context(snapshot),
        "trace_refs": trace_references(os.environ.get("AUTO_MERGE_TRACE_REFS_FILE", "")),
        "policy": policy,
        "prerequisites": evaluation,
        "semantic_context": evaluation["semantic_context"],
    }
    document["context_fingerprint"] = canonical_hash(document)
    document["binding"]["context_fingerprint"] = document["context_fingerprint"]
    return document


def read_quality(path: str) -> dict[str, Any]:
    if not path:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("Review quality evidence file is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise GateError("Review quality evidence must be a JSON object")
    return value


def policy_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "repository": args.repository,
        "base_ref": args.base_ref,
        "policy_version": args.policy_version,
        "mode": args.mode,
        "semantic_reviewer": args.semantic_reviewer,
        "semantic_provider": args.semantic_provider,
        "review_attestation_file": args.review_attestation_file,
        "risk_assessment_producer": args.risk_assessment_producer,
        "artifact_correlation_minutes": args.artifact_correlation_minutes,
        "maximum_unattended_risk": args.maximum_unattended_risk,
        "human_signal_associations": sorted(csv_values(args.human_signal_associations)),
        "review_quality_mode": args.review_quality_mode,
        "review_quality_minimum_score": args.review_quality_minimum_score,
        "review_quality_minimum_samples": args.review_quality_minimum_samples,
        "custom_instructions": args.custom_instructions,
    }


def collect_command(args: argparse.Namespace) -> int:
    match = ISSUE_URL_RE.fullmatch(args.issue_url)
    if not match or match.group("repo") != args.repository:
        raise GateError("ISSUE_URL must identify a pull request in the configured repository")
    policy = policy_from_args(args)
    snapshot = collect_snapshot(args.repository, int(match.group("number")), read_quality(args.review_quality_file))
    evidence = build_evidence(snapshot, policy)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--issue-url", required=True)
    collect.add_argument("--repository", required=True)
    collect.add_argument("--base-ref", required=True)
    collect.add_argument("--policy-version", required=True)
    collect.add_argument("--mode", required=True, choices=["observe", "lab-automatic"])
    collect.add_argument("--semantic-reviewer", required=True)
    collect.add_argument("--semantic-provider", default="fullsend-review-agent")
    collect.add_argument("--review-attestation-file", default="")
    collect.add_argument("--risk-assessment-producer", required=True)
    collect.add_argument("--artifact-correlation-minutes", required=True, type=int)
    collect.add_argument("--maximum-unattended-risk", required=True, choices=["low", "moderate", "elevated", "high", "critical"])
    collect.add_argument("--human-signal-associations", required=True)
    collect.add_argument("--review-quality-mode", required=True, choices=sorted(QUALITY_MODES))
    collect.add_argument("--review-quality-minimum-score", required=True, type=float)
    collect.add_argument("--review-quality-minimum-samples", required=True, type=int)
    collect.add_argument("--review-quality-file", default="")
    collect.add_argument("--custom-instructions", required=True)
    collect.add_argument("--output", required=True)
    collect.set_defaults(func=collect_command)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return args.func(args)
    except (GateError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"auto-merge semantic preflight failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
