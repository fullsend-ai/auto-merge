#!/usr/bin/env python3
"""One expiring owner-authorized lab merge; never a production qualification."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

import github_observe as g
from platform_lab import (
    ROOT,
    InputError,
    assess,
    digest,
    load,
    require,
    source_digests,
    utc,
    validate,
)

REPO = g.REPOSITORY
BASE = "repos/" + REPO + "/"
DOCUMENT = "docs/example-feature.md"
QUEUE_CHECK = "Gemara pilot queue gate"
CHECKS = g.CHECK_NAMES | {"Merge group proof"}
GROUP_REF = re.compile(
    r"refs/heads/gh-readonly-queue/main/pr-([1-9][0-9]*)-([0-9a-f]{40})\Z"
)


def grant():
    data = load(ROOT / "policies/live-pilot-grant.json")
    require(
        set(data)
        == {
            "schema_version",
            "repository",
            "enabled",
            "pull_request",
            "head_sha",
            "expires_at",
            "maximum_changed_lines",
        },
        "invalid_pilot_grant",
    )
    require(
        data["schema_version"] == "lab-merge-grant/v1"
        and data["repository"] == REPO
        and data["enabled"] is True,
        "pilot_not_enabled",
    )
    require(
        type(data["pull_request"]) is int and 0 < data["pull_request"] < 1000000,
        "invalid_pilot_grant",
    )
    require(
        isinstance(data["head_sha"], str)
        and re.fullmatch("[0-9a-f]{40}", data["head_sha"]),
        "invalid_pilot_grant",
    )
    require(
        type(data["maximum_changed_lines"]) is int
        and 1 <= data["maximum_changed_lines"] <= 20,
        "invalid_pilot_grant",
    )
    remaining = (utc(data["expires_at"]) - datetime.now(timezone.utc)).total_seconds()
    require(0 < remaining <= 86400, "pilot_grant_expired_or_too_long")
    return data


def bundle():
    catalog = load(ROOT / "policies/live-pilot-controls.json")
    policy = load(ROOT / "policies/live-pilot-policy.json")
    validate(catalog, "ControlCatalog")
    validate(policy, "Policy")
    return {
        "root_policy": policy["metadata"]["id"],
        "catalogs": {catalog["metadata"]["id"]: catalog},
        "policies": {policy["metadata"]["id"]: policy},
    }


def checks_pass(rows, sha):
    if rows is None:
        return False
    for name in CHECKS:
        matches = [
            r
            for r in rows
            if r.get("name") == name
            and r.get("head_sha") == sha
            and (r.get("app") or {}).get("id") == 15368
        ]
        if (
            len(matches) != 1
            or matches[0].get("status") != "completed"
            or matches[0].get("conclusion") != "success"
        ):
            return False
    return True


def queue_rules(rows):
    if not isinstance(rows, list):
        return False
    kinds = {r.get("type") for r in rows}
    queues = [r for r in rows if r.get("type") == "merge_queue"]
    required = [r for r in rows if r.get("type") == "required_status_checks"]
    reviews = [r for r in rows if r.get("type") == "pull_request"]
    contexts = {
        (c.get("context"), c.get("integration_id"))
        for r in required
        for c in r.get("parameters", {}).get("required_status_checks", [])
    }
    return (
        {"deletion", "non_fast_forward"} <= kinds
        and len(queues) == 1
        and queues[0].get("parameters", {}).get("max_entries_to_merge") == 1
        and queues[0].get("parameters", {}).get("max_entries_to_build") == 1
        and all((n, 15368) in contexts for n in CHECKS | {QUEUE_CHECK})
        and all(
            r.get("parameters", {}).get("strict_required_status_checks_policy") is True
            for r in required
        )
        and len(reviews) == 1
        and reviews[0].get("parameters", {}).get("required_approving_review_count", 0)
        >= 1
        and reviews[0].get("parameters", {}).get("dismiss_stale_reviews_on_push")
        is True
        and reviews[0].get("parameters", {}).get("required_review_thread_resolution")
        is True
    )


def tree(client, sha):
    value = client.get(BASE + f"git/trees/{sha}?recursive=1")
    require(value is not None and not value.get("truncated"), "pilot_tree_incomplete")
    return {
        r["path"]: (r["type"], r["mode"], r["sha"])
        for r in value.get("tree", [])
        if r.get("type") != "tree"
    }


def scoped(files, maximum):
    return (
        isinstance(files, list)
        and len(files) == 1
        and files[0].get("filename") == DOCUMENT
        and files[0].get("status") == "modified"
        and not files[0].get("previous_filename")
        and type(files[0].get("changes")) is int
        and 0 < files[0]["changes"] <= maximum
    )


def exact_tree(base, reviewed, queued):
    doc = reviewed.get(DOCUMENT)
    return (
        doc is not None
        and doc[:2] == ("blob", "100644")
        and queued.get(DOCUMENT) == doc
        and {k: v for k, v in base.items() if k != DOCUMENT}
        == {k: v for k, v in queued.items() if k != DOCUMENT}
    )


def trusted_source(client, base_sha, phase, group_sha=None):
    source = os.environ.get("PILOT_SOURCE_SHA")
    if source != base_sha or not re.fullmatch("[0-9a-f]{40}", source or ""):
        return False
    if phase == "enroll" and (
        os.environ.get("PILOT_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("PILOT_REF") != "refs/heads/main"
    ):
        return False
    if phase == "queue" and os.environ.get("PILOT_EVENT_NAME") != "merge_group":
        return False
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not re.fullmatch("[1-9][0-9]{0,14}", run_id) or not re.fullmatch(
        "[1-9][0-9]{0,5}", attempt
    ):
        return False
    run = client.get(BASE + f"actions/runs/{run_id}")
    expected_path = ".github/workflows/autonomy-" + (
        "pilot.yml" if phase == "enroll" else "queue.yml"
    )
    if not run or not (
        run.get("event") == os.environ["PILOT_EVENT_NAME"]
        and run.get("path") == expected_path
        and run.get("head_sha") == (group_sha or source)
        and run.get("run_attempt") == int(attempt)
        and run.get("repository", {}).get("full_name") == REPO
    ):
        return False
    remote = tree(client, source)
    paths = ["experiments/autonomy-platform/" + p for p in source_digests()]
    paths += [
        ".github/workflows/autonomy-pilot.yml",
        ".github/workflows/autonomy-queue.yml",
    ]
    for name in paths:
        path = ROOT.parents[1] / name
        if not path.is_file() or path.is_symlink():
            return False
        raw = path.read_bytes()
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if remote.get(name) != ("blob", "100644", oid):
            return False
    return True


def discussions_clear(client, number):
    # A fixed read-only query. No caller-provided GraphQL or mutation is accepted.
    query = 'query($number:Int!,$cursor:String){repository(owner:"fullsend-ai",name:"auto-merge"){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{isResolved} pageInfo{hasNextPage endCursor}}}}}'
    cursor = None
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {"Content-Type": "application/json", "User-Agent": "gemara-live-pilot"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        for _ in range(10):
            request = urllib.request.Request(
                "https://api.github.com/graphql",
                data=json.dumps(
                    {"query": query, "variables": {"number": number, "cursor": cursor}}
                ).encode(),
                headers=headers,
                method="POST",
            )
            with client.opener.open(request, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "pilot_threads_too_large")
            data = json.loads(raw)
            if data.get("errors"):
                return False
            result = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            if not all(n.get("isResolved") is True for n in result["nodes"]):
                return False
            if not result["pageInfo"]["hasNextPage"]:
                break
            cursor = result["pageInfo"]["endCursor"]
            if not isinstance(cursor, str) or len(cursor) > 500:
                return False
        else:
            return False
        reviews = client.pages(BASE + f"pulls/{number}/reviews")
        if reviews is None:
            return False
        latest = {}
        for review in reviews:
            if review.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
                identity = (review.get("user") or {}).get("id")
                if type(identity) is not int:
                    return False
                if review.get("id", 0) > latest.get(identity, {}).get("id", 0):
                    latest[identity] = review
        return all(r["state"] != "CHANGES_REQUESTED" for r in latest.values())
    except Exception:
        return False


def queue_entry_matches(entry, number, head, base, group):
    return bool(
        entry
        and entry.get("position") == 1
        and (entry.get("pullRequest") or {}).get("number") == number
        and (entry.get("pullRequest") or {}).get("headRefOid") == head
        and (entry.get("baseCommit") or {}).get("oid") == base
        and (entry.get("headCommit") or {}).get("oid") == group
    )


def queued_revision(client, number, head, base, group):
    query = 'query($number:Int!){repository(owner:"fullsend-ai",name:"auto-merge"){pullRequest(number:$number){mergeQueueEntry{position baseCommit{oid} headCommit{oid} pullRequest{number headRefOid}}}}}'
    headers = {"Content-Type": "application/json", "User-Agent": "gemara-live-pilot"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"number": number}}).encode(),
            headers=headers,
            method="POST",
        )
        with client.opener.open(request, timeout=20) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            return False
        data = json.loads(raw)
        if data.get("errors"):
            return False
        entry = data["data"]["repository"]["pullRequest"]["mergeQueueEntry"]
        return queue_entry_matches(entry, number, head, base, group)
    except Exception:
        return False


def wait_queue_ci(client, sha):
    for _ in range(32):
        rows = client.pages(
            BASE + f"commits/{sha}/check-runs?filter=latest", "check_runs"
        )
        if checks_pass(rows, sha):
            return True
        if rows is None or any(
            r.get("name") in CHECKS
            and r.get("status") == "completed"
            and r.get("conclusion") != "success"
            for r in rows
        ):
            return False
        time.sleep(15)
    return False


def evaluate(number, expected_head, phase, client=None):
    permission = grant()
    require(
        number == permission["pull_request"]
        and expected_head == permission["head_sha"],
        "pilot_grant_does_not_match",
    )
    client = client or g.Client()
    group_sha = os.environ.get("PILOT_GROUP_SHA") if phase == "queue" else None
    group_base = os.environ.get("PILOT_GROUP_BASE") if phase == "queue" else None
    if phase == "queue":
        require(
            re.fullmatch("[0-9a-f]{40}", group_sha or "")
            and re.fullmatch("[0-9a-f]{40}", group_base or ""),
            "invalid_merge_group",
        )
        match = GROUP_REF.fullmatch(os.environ.get("PILOT_GROUP_REF", ""))
        require(
            match is not None and int(match[1]) == number and match[2] == group_base,
            "unrecognized_merge_group",
        )
        group_ci = wait_queue_ci(client, group_sha)
    report = g.observe(number, client)
    current_head, base_sha = report["head_sha"], report["base_sha"]
    target = group_sha or current_head
    files = client.pages(BASE + f"pulls/{number}/files")
    source_ok = trusted_source(client, base_sha, phase, group_sha)
    base_tree, reviewed_tree = tree(client, base_sha), tree(client, current_head)
    scope_ok = scoped(files, permission["maximum_changed_lines"]) and reviewed_tree.get(
        DOCUMENT, ()
    )[:2] == ("blob", "100644")
    if phase == "queue":
        scope_ok = (
            scope_ok
            and group_base == base_sha
            and exact_tree(base_tree, reviewed_tree, tree(client, group_sha))
            and queued_revision(client, number, expected_head, base_sha, group_sha)
        )
    ci = (
        group_ci
        if phase == "queue"
        else checks_pass(
            client.pages(
                BASE + f"commits/{target}/check-runs?filter=latest", "check_runs"
            ),
            target,
        )
    )
    values = {
        "LP-AUTH": current_head == expected_head and report["pr_open"],
        "LP-SCOPE": scope_ok,
        "LP-SOURCE": source_ok,
        "LP-CANDIDATE": report["stable_during_collection"]
        and report["candidate_decision"] == "eligible",
        "LP-CI": ci,
        "LP-RULES": queue_rules(client.get(BASE + "rules/branches/main")),
        "LP-DISCUSSION": discussions_clear(client, number),
    }
    now = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    context = {
        "grant": permission,
        "stage": phase,
        "reviewed_head": expected_head,
        "evaluated_sha": target,
        "base_sha": base_sha,
        "candidate_request": report["shadow"]["evaluation"]["request_sha256"],
    }
    subject = {
        "repository": REPO,
        "branch": "main",
        "configuration_sha256": digest(context),
        "head_sha": target,
        "base_sha": base_sha,
    }
    observations = {
        k: {
            "subject_sha256": digest(subject),
            "collected_at": now,
            "trusted_source": not client.errors,
            "value": bool(v),
        }
        for k, v in values.items()
    }
    result = assess(bundle(), "candidate", subject, observations, now)
    again = client.get(BASE + f"pulls/{number}")
    branch = client.get(BASE + "branches/main")
    require(
        again
        and again["head"]["sha"] == expected_head
        and again["state"] == "open"
        and not again.get("draft")
        and branch
        and branch["commit"]["sha"] == base_sha
        and grant() == permission
        and not client.errors,
        "pilot_state_changed",
    )
    return {
        "schema_version": "lab-pilot-result/v1",
        "repository": REPO,
        "pull_request": number,
        "stage": phase,
        "reviewed_head": expected_head,
        "evaluated_sha": target,
        "base_sha": base_sha,
        "grant_sha256": digest(permission),
        "decision": result["decision"],
        "production_readiness": report["readiness_decision"],
        "evaluation": result,
        "authorized_action": "enqueue-only"
        if phase == "enroll" and result["decision"] == "eligible"
        else "none",
    }


def enqueue(result):
    require(
        result["decision"] == "eligible"
        and result["stage"] == "enroll"
        and os.environ.get("PILOT_CAN_ENQUEUE") == "true",
        "pilot_enqueue_not_authorized",
    )
    # GitHub enforces its protected merge queue. Never use --admin or a direct merge API.
    command = [
        "gh",
        "pr",
        "merge",
        str(result["pull_request"]),
        "-R",
        REPO,
        "--auto",
        "--match-head-commit",
        result["reviewed_head"],
    ]
    child = subprocess.run(command, capture_output=True, text=True, timeout=60)
    require(child.returncode == 0, "github_queue_request_failed")
    return "queue_request_submitted"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["enroll", "queue"], required=True)
    parser.add_argument("--pr", type=int)
    parser.add_argument("--head")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        number, head = args.pr, args.head
        if args.phase == "queue":
            match = GROUP_REF.fullmatch(os.environ.get("PILOT_GROUP_REF", ""))
            require(match is not None, "unrecognized_merge_group")
            number, head = int(match[1]), grant()["head_sha"]
        require(
            type(number) is int
            and 0 < number < 1000000
            and isinstance(head, str)
            and re.fullmatch("[0-9a-f]{40}", head),
            "invalid_pilot_request",
        )
        result = evaluate(number, head, args.phase)
        compact = {k: v for k, v in result.items() if k != "evaluation"}
        compact["assessments"] = [
            {k: r[k] for k in ["id", "state", "reason"]}
            for r in result["evaluation"]["assessments"]
        ]
        print(json.dumps(compact), flush=True)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            Path(summary).write_text(
                "# Owner-authorized lab merge pilot\n\n"
                + f"PR #{number}; evaluated `{result['evaluated_sha']}`; stage {args.phase}; decision **{result['decision']}**. Production qualification: **{result['production_readiness']}**.\n\n"
                + "\n".join(
                    f"- {r['id']}: {r['state']} ({r['reason']})"
                    for r in compact["assessments"]
                )
                + "\n"
            )
        require(result["decision"] == "eligible", "pilot_policy_held")
        if args.execute:
            print(
                json.dumps(
                    {
                        "action": enqueue(result),
                        "pull_request": number,
                        "head_sha": head,
                    }
                )
            )
        return 0
    except InputError as exc:
        print(json.dumps({"decision": "hold", "error": str(exc), "action": "none"}))
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "decision": "hold",
                    "error": "pilot_evaluation_failed",
                    "action": "none",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
