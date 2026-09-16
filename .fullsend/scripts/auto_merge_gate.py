#!/usr/bin/env python3
"""Collect and evaluate exact-head GitHub pull-request merge evidence."""

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


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_URL_RE = re.compile(
    r"^https://github\.com/(?P<repo>[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)/"
    r"(?:pull|issues)/(?P<number>[1-9][0-9]*)$"
)
SIGNOFF_RE = re.compile(r"(?im)^Signed-off-by:\s+[^<\n]+<[^>\n]+>\s*$")
DENY_LABELS = {"do-not-merge", "hold", "fullsend-no-merge", "security-review-required"}


class GateError(RuntimeError):
    """A forge lookup or evidence-integrity failure."""


def canonical_hash(document: dict[str, Any]) -> str:
    unsigned = json.loads(json.dumps(document))
    unsigned.pop("evidence_sha256", None)
    if isinstance(unsigned.get("binding"), dict):
        unsigned["binding"].pop("evidence_sha256", None)
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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


def collect_snapshot(repository: str, number: int) -> dict[str, Any]:
    pr = gh_json("api", f"repos/{repository}/pulls/{number}")
    head_sha = pr.get("head", {}).get("sha", "")
    if not SHA_RE.fullmatch(head_sha):
        raise GateError("pull request returned an invalid head SHA")

    files = gh_json("api", f"repos/{repository}/pulls/{number}/files?per_page=100")
    reviews = gh_json("api", f"repos/{repository}/pulls/{number}/reviews?per_page=100")
    commits = gh_json("api", f"repos/{repository}/pulls/{number}/commits?per_page=100")
    checks_obj = gh_json(
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        f"repos/{repository}/commits/{head_sha}/check-runs?per_page=100",
    )
    owner, name = repository.split("/", 1)
    threads_obj = gh_json(
        "api",
        "graphql",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
        "-F",
        f"number={number}",
        "-f",
        "query=query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved} pageInfo{hasNextPage}}}}}",
    )
    threads = (
        threads_obj.get("data", {})
        .get("repository", {})
        .get("pullRequest", {})
        .get("reviewThreads", {})
    )

    return {
        "pull_request": pr,
        "files": files,
        "reviews": reviews,
        "commits": commits,
        "check_runs": checks_obj.get("check_runs", []),
        "review_threads": threads,
    }


def _latest_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        state = str(review.get("state", "")).upper()
        if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        login = str((review.get("user") or {}).get("login", ""))
        if not login:
            continue
        prior = latest.get(login)
        key = (str(review.get("submitted_at") or ""), int(review.get("id") or 0))
        prior_key = (
            str((prior or {}).get("submitted_at") or ""),
            int((prior or {}).get("id") or 0),
        )
        if prior is None or key > prior_key:
            latest[login] = review
    return list(latest.values())


def _latest_checks(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for check in checks:
        name = str(check.get("name", ""))
        if not name:
            continue
        prior = latest.get(name)
        key = (str(check.get("completed_at") or check.get("started_at") or ""), int(check.get("id") or 0))
        prior_key = (
            str((prior or {}).get("completed_at") or (prior or {}).get("started_at") or ""),
            int((prior or {}).get("id") or 0),
        )
        if prior is None or key > prior_key:
            latest[name] = check
    return latest


def evaluate_snapshot(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pr = snapshot["pull_request"]
    repository = policy["repository"]
    head_sha = str((pr.get("head") or {}).get("sha", ""))
    base_sha = str((pr.get("base") or {}).get("sha", ""))
    failures: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            failures.append(reason)

    require(pr.get("state") == "open", "pull request is not open")
    require(pr.get("draft") is False, "pull request is a draft")
    require(SHA_RE.fullmatch(head_sha) is not None, "head SHA is invalid")
    require(SHA_RE.fullmatch(base_sha) is not None, "base SHA is invalid")
    require((pr.get("base") or {}).get("ref") == policy["base_ref"], "base ref is not allowed")
    require((pr.get("base") or {}).get("repo", {}).get("full_name") == repository, "base repository mismatch")
    require((pr.get("head") or {}).get("repo", {}).get("full_name") == repository, "fork pull requests are not allowed")
    require(pr.get("mergeable") is True, "mergeability is false or unknown")
    require(pr.get("mergeable_state") == "clean", "mergeable state is not clean")
    require(pr.get("auto_merge") is None, "native standing auto-merge is enabled")

    author = str((pr.get("user") or {}).get("login", ""))
    require(author in policy["allowed_authors"], f"author {author or '<unknown>'} is not allowed")
    labels = sorted(str(label.get("name", "")) for label in pr.get("labels", []))
    blocked = sorted({label.lower() for label in labels} & DENY_LABELS)
    require(not blocked, "hold label present: " + ", ".join(blocked))

    files = snapshot["files"]
    changed_paths = sorted(str(item.get("filename", "")) for item in files)
    require(0 < len(changed_paths) <= 3, "changed file count is outside the 1-3 file cohort")
    disallowed = [path for path in changed_paths if path not in policy["allowed_paths"]]
    require(not disallowed, "disallowed changed path: " + ", ".join(disallowed))
    require(len(files) < 100, "changed-file result may be truncated")

    latest_checks = _latest_checks(snapshot["check_runs"])
    check_evidence: list[dict[str, Any]] = []
    for name in policy["required_checks"]:
        check = latest_checks.get(name)
        check_evidence.append(
            {
                "name": name,
                "status": (check or {}).get("status", "missing"),
                "conclusion": (check or {}).get("conclusion", "missing"),
                "head_sha": (check or {}).get("head_sha", ""),
            }
        )
        require(check is not None, f"required check is missing: {name}")
        if check is not None:
            require(check.get("head_sha") == head_sha, f"required check is stale: {name}")
            require(check.get("status") == "completed", f"required check is pending: {name}")
            require(check.get("conclusion") == "success", f"required check did not succeed: {name}")

    latest_reviews = _latest_reviews(snapshot["reviews"])
    changes_requested = [
        (review.get("user") or {}).get("login", "unknown")
        for review in latest_reviews
        if review.get("state") == "CHANGES_REQUESTED"
    ]
    approvals = [
        review
        for review in latest_reviews
        if review.get("state") == "APPROVED" and review.get("commit_id") == head_sha
    ]
    require(not changes_requested, "changes-requested review remains: " + ", ".join(changes_requested))
    require(bool(approvals), "no approval applies to the exact head SHA")

    threads = snapshot.get("review_threads") or {}
    thread_nodes = threads.get("nodes") or []
    unresolved_count = sum(1 for thread in thread_nodes if not thread.get("isResolved"))
    require(not (threads.get("pageInfo") or {}).get("hasNextPage", False), "review-thread result is truncated")
    require(unresolved_count == 0, f"{unresolved_count} unresolved review thread(s) remain")

    commits = snapshot["commits"]
    require(0 < len(commits) < 100, "commit list is empty or may be truncated")
    unsigned = []
    commit_evidence = []
    for commit in commits:
        sha = str(commit.get("sha", ""))
        signed = SIGNOFF_RE.search(str((commit.get("commit") or {}).get("message", ""))) is not None
        commit_evidence.append({"sha": sha, "dco_signed_off": signed})
        if not signed:
            unsigned.append(sha[:12] or "unknown")
    require(not unsigned, "commit lacks DCO sign-off: " + ", ".join(unsigned))

    return {
        "eligible": not failures,
        "failures": failures,
        "changed_paths": changed_paths,
        "labels": labels,
        "checks": check_evidence,
        "approvals": [
            {"login": (review.get("user") or {}).get("login", ""), "commit_id": review.get("commit_id", "")}
            for review in approvals
        ],
        "changes_requested_by": changes_requested,
        "unresolved_review_threads": unresolved_count,
        "commits": commit_evidence,
    }


def build_evidence(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pr = snapshot["pull_request"]
    evaluation = evaluate_snapshot(snapshot, policy)
    document: dict[str, Any] = {
        "schema_version": "1",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "binding": {
            "repository": policy["repository"],
            "pull_request_number": int(pr["number"]),
            "head_sha": pr["head"]["sha"],
            "base_ref": pr["base"]["ref"],
            "base_sha": pr["base"]["sha"],
            "policy_version": policy["policy_version"],
        },
        "pull_request": {
            "url": pr.get("html_url", ""),
            "title": str(pr.get("title", ""))[:500],
            "body": str(pr.get("body") or "")[:8000],
            "author": (pr.get("user") or {}).get("login", ""),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "changed_files": pr.get("changed_files", 0),
            "mergeable": pr.get("mergeable"),
            "mergeable_state": pr.get("mergeable_state"),
            "native_auto_merge_enabled": pr.get("auto_merge") is not None,
        },
        "policy": policy,
        "deterministic": evaluation,
    }
    document["evidence_sha256"] = canonical_hash(document)
    document["binding"]["evidence_sha256"] = document["evidence_sha256"]
    return document


def collect_command(args: argparse.Namespace) -> int:
    match = ISSUE_URL_RE.fullmatch(args.issue_url)
    if not match:
        raise GateError("ISSUE_URL must be a GitHub pull-request URL")
    if match.group("repo") != args.repository:
        raise GateError("ISSUE_URL repository does not match the configured repository")
    policy = {
        "repository": args.repository,
        "base_ref": args.base_ref,
        "policy_version": args.policy_version,
        "required_checks": csv_values(args.required_checks),
        "allowed_paths": csv_values(args.allowed_paths),
        "allowed_authors": csv_values(args.allowed_authors),
    }
    if not policy["required_checks"] or not policy["allowed_paths"] or not policy["allowed_authors"]:
        raise GateError("required checks, allowed paths, and allowed authors must be non-empty")
    snapshot = collect_snapshot(args.repository, int(match.group("number")))
    document = build_evidence(snapshot, policy)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--issue-url", required=True)
    collect.add_argument("--repository", required=True)
    collect.add_argument("--base-ref", required=True)
    collect.add_argument("--policy-version", required=True)
    collect.add_argument("--required-checks", required=True)
    collect.add_argument("--allowed-paths", required=True)
    collect.add_argument("--allowed-authors", required=True)
    collect.add_argument("--output", required=True)
    collect.set_defaults(func=collect_command)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except (GateError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"auto-merge gate failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
