#!/usr/bin/env python3
"""Bounded repeatable auto-merge pilot with exact-head maintainer maintenance."""

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
from app_token import verify_scope
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


def configuration():
    data = load(ROOT / "policies/pilot-config.json")
    require(
        set(data)
        == {
            "schema_version",
            "repository",
            "automatic_enabled",
            "automatic_expires_at",
            "maintenance_enabled",
            "allowed_document_paths",
            "maximum_changed_lines",
            "maintenance_maximum_age_seconds",
        },
        "invalid_pilot_configuration",
    )
    require(
        data["schema_version"] == "repository-merge-pilot/v1"
        and data["repository"] == REPO
        and type(data["automatic_enabled"]) is bool
        and type(data["maintenance_enabled"]) is bool,
        "invalid_pilot_configuration",
    )
    require(
        isinstance(data["automatic_expires_at"], str), "invalid_pilot_configuration"
    )
    utc(data["automatic_expires_at"])
    # Finite lab cohort: no globs, executable paths, or caller-selected policies.
    require(
        data["allowed_document_paths"] == [DOCUMENT]
        and type(data["maximum_changed_lines"]) is int
        and 1 <= data["maximum_changed_lines"] <= 20
        and type(data["maintenance_maximum_age_seconds"]) is int
        and 60 <= data["maintenance_maximum_age_seconds"] <= 3600,
        "invalid_pilot_configuration",
    )
    return data


def bundle(maintenance=False):
    prefix = "maintenance" if maintenance else "live-pilot"
    catalog = load(ROOT / f"policies/{prefix}-controls.json")
    policy = load(ROOT / f"policies/{prefix}-policy.json")
    validate(catalog, "ControlCatalog")
    validate(policy, "Policy")
    return {
        "root_policy": policy["metadata"]["id"],
        "catalogs": {catalog["metadata"]["id"]: catalog},
        "policies": {policy["metadata"]["id"]: policy},
    }


def checks_pass(rows, sha, names=None):
    if rows is None:
        return False
    for name in CHECKS if names is None else names:
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
        and reviews[0].get("parameters", {}).get("required_approving_review_count", -1)
        >= 0
        and reviews[0].get("parameters", {}).get("dismiss_stale_reviews_on_push")
        is True
        and reviews[0].get("parameters", {}).get("require_code_owner_review") is True
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


def maintenance_scope(files):
    return bool(
        isinstance(files, list)
        and 0 < len(files) <= 100
        and sum(r.get("changes", 10001) for r in files) <= 10000
        and all(
            isinstance(r.get("filename"), str)
            and r["filename"].startswith("docs/")
            and r["filename"] != "docs/AUTO-MERGE-SECURITY-CONTRACT.md"
            and r["filename"].rsplit("/", 1)[-1] != "AGENTS.md"
            and r.get("status") in {"modified", "added", "removed"}
            and not r.get("previous_filename")
            for r in files
        )
    )


def maintenance_tree(base, reviewed, queued, files):
    changed = {r["filename"] for r in files}
    return bool(
        maintenance_scope(files)
        and all(
            queued.get(name) == reviewed.get(name)
            and all(
                entry is None or entry[:2] in {("blob", "100644"), ("blob", "100755")}
                for entry in (base.get(name), reviewed.get(name))
            )
            for name in changed
        )
        and {k: v for k, v in base.items() if k not in changed}
        == {k: v for k, v in queued.items() if k not in changed}
    )


def maintenance_run_matches(run, number, head, base, maximum_age, queue_phase):
    try:
        age = (datetime.now(timezone.utc) - utc(run["created_at"])).total_seconds()
        return bool(
            run.get("event") == "workflow_dispatch"
            and run.get("path") == ".github/workflows/autonomy-pilot.yml"
            and run.get("head_sha") == base
            and run.get("repository", {}).get("full_name") == REPO
            and run.get("display_title")
            == f"Gemara maintenance execute PR #{number} @{head}"
            and type(run.get("id")) is int
            and run["id"] > 0
            and type(run.get("run_attempt")) is int
            and run["run_attempt"] > 0
            and 0 <= age <= maximum_age
            and (
                not queue_phase
                or (
                    run.get("status") in {"in_progress", "completed"}
                    and run.get("conclusion") in {None, "success"}
                )
            )
        )
    except (KeyError, ValueError, InputError, TypeError):
        return False


def independent_maintenance_approval(client, number, head):
    pr = client.get(BASE + f"pulls/{number}")
    if not pr or pr.get("head", {}).get("sha") != head:
        return None
    authors = {pr.get("user", {}).get("login", "").lower()}
    commits = client.pages(BASE + f"pulls/{number}/commits")
    if not isinstance(commits, list) or not commits or "" in authors:
        return None
    for commit in commits:
        login = (commit.get("author") or {}).get("login")
        if not isinstance(login, str):
            return None
        authors.add(login.lower())
    reviews = client.pages(BASE + f"pulls/{number}/reviews")
    if not isinstance(reviews, list):
        return None
    latest = {}
    for review in reviews:
        if review.get("state") not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        user = review.get("user") or {}
        login = user.get("login", "")
        if user.get("type") != "User" or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
            continue
        if type(review.get("id")) is not int:
            return None
        if review["id"] > latest.get(login.lower(), {}).get("id", 0):
            latest[login.lower()] = review
    for login, review in latest.items():
        if (
            login in authors
            or review["state"] != "APPROVED"
            or review.get("commit_id") != head
        ):
            continue
        permission = client.get(BASE + f"collaborators/{login}/permission")
        if permission and permission.get("role_name", permission.get("permission")) in {
            "admin",
            "maintain",
        }:
            return {"review_id": review["id"], "reviewed_head": head}
    return None


def maintenance_authorization(client, number, head, base, phase, config):
    if not config["maintenance_enabled"]:
        return None
    if phase == "enroll":
        if os.environ.get("PILOT_MAINTENANCE") != "true":
            return None
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        if not re.fullmatch("[1-9][0-9]{0,14}", run_id):
            return None
        rows = [client.get(BASE + f"actions/runs/{run_id}")]
    else:
        rows = []
        previous = datetime.now(timezone.utc)
        for page in range(1, 11):
            value = client.get(
                BASE
                + f"actions/workflows/autonomy-pilot.yml/runs?event=workflow_dispatch&per_page=100&page={page}"
            )
            batch = (value or {}).get("workflow_runs")
            require(isinstance(batch, list), "maintenance_search_incomplete")
            reached_boundary = False
            for candidate in batch:
                created = utc(candidate.get("created_at"))
                require(created <= previous, "maintenance_search_order_unknown")
                previous = created
                if (datetime.now(timezone.utc) - created).total_seconds() > config[
                    "maintenance_maximum_age_seconds"
                ]:
                    reached_boundary = True
                    break
                rows.append(candidate)
            if reached_boundary or len(batch) < 100:
                break
        else:
            raise InputError("maintenance_search_incomplete")
    for run in rows:
        if not run or not maintenance_run_matches(
            run,
            number,
            head,
            base,
            config["maintenance_maximum_age_seconds"],
            phase == "queue",
        ):
            continue
        if phase == "queue":
            jobs = client.get(
                BASE
                + f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100"
            )
            rows = (jobs or {}).get("jobs", [])
            evaluations = [
                job
                for job in rows
                if job.get("name") in {"evaluate", "enqueue / writer"}
            ]
            if (
                not jobs
                or jobs.get("total_count", 101) > 100
                or {job.get("name") for job in evaluations}
                != {"evaluate", "enqueue / writer"}
                or len(evaluations) != 2
                or any(
                    job.get("run_id") != run["id"]
                    or job.get("head_sha") != base
                    or job.get("status") != "completed"
                    or job.get("conclusion") != "success"
                    for job in evaluations
                )
            ):
                continue
        actors = [run.get("actor"), run.get("triggering_actor")]
        if not all(
            isinstance(actor, dict)
            and re.fullmatch(r"[A-Za-z0-9-]{1,39}", actor.get("login", ""))
            for actor in actors
        ):
            continue
        approved = True
        for actor in actors:
            permission = client.get(BASE + f"collaborators/{actor['login']}/permission")
            if not permission or permission.get(
                "role_name", permission.get("permission")
            ) not in {"admin", "maintain"}:
                approved = False
        approval = (
            independent_maintenance_approval(client, number, head) if approved else None
        )
        if approval:
            return {
                "independent_approval": approval,
                "run_id": run["id"],
                "run_attempt": run["run_attempt"],
                "head_sha": head,
                "source_sha": base,
                "authorization": "maintainer-workflow-dispatch",
            }
    return None


def trusted_source(client, base_sha, phase, group_sha=None):
    source = os.environ.get("PILOT_SOURCE_SHA")
    if source != base_sha or not re.fullmatch("[0-9a-f]{40}", source or ""):
        return False
    if phase == "enroll" and (
        os.environ.get("PILOT_EVENT_NAME") not in {"workflow_dispatch", "workflow_run"}
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
        ".github/workflows/gemara-writer.yml",
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


def current_pr(pr, head):
    return bool(
        pr
        and pr.get("state") == "open"
        and pr.get("draft") is False
        and pr.get("mergeable") is True
        and (pr.get("head") or {}).get("sha") == head
        and ((pr.get("head") or {}).get("repo") or {}).get("full_name") == REPO
        and (pr.get("base") or {}).get("ref") == "main"
        and ((pr.get("base") or {}).get("repo") or {}).get("full_name") == REPO
    )


def evaluate(number, expected_head, phase, client=None):
    config = configuration()
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
    pr = client.get(BASE + f"pulls/{number}")
    branch = client.get(BASE + "branches/main")
    require(current_pr(pr, expected_head) and branch, "pilot_candidate_not_current")
    base_sha = branch["commit"]["sha"]
    permission = maintenance_authorization(
        client, number, expected_head, base_sha, phase, config
    )
    maintenance = permission is not None
    if phase == "enroll" and os.environ.get("PILOT_MAINTENANCE") == "true":
        require(maintenance, "maintenance_authorization_missing")
    automatic_authorized = bool(
        config["automatic_enabled"]
        and datetime.now(timezone.utc) < utc(config["automatic_expires_at"])
        and current_pr(pr, expected_head)
    )
    report = None if maintenance else g.observe(number, client)
    current_head = pr["head"]["sha"]
    target = group_sha or current_head
    files = client.pages(BASE + f"pulls/{number}/files")
    source_ok = trusted_source(client, base_sha, phase, group_sha)
    base_tree, reviewed_tree = tree(client, base_sha), tree(client, current_head)
    scope_ok = (
        maintenance_scope(files)
        if maintenance
        else scoped(files, config["maximum_changed_lines"])
        and reviewed_tree.get(DOCUMENT, ())[:2] == ("blob", "100644")
    )
    if phase == "queue":
        queued = tree(client, group_sha)
        scope_ok = (
            scope_ok
            and group_base == base_sha
            and (
                maintenance_tree(base_tree, reviewed_tree, queued, files)
                if maintenance
                else exact_tree(base_tree, reviewed_tree, queued)
            )
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
    if maintenance:
        ci = ci and checks_pass(
            client.pages(
                BASE + f"commits/{expected_head}/check-runs?filter=latest", "check_runs"
            ),
            expected_head,
            {"Gemara integration tests"},
        )
    values = {
        "LP-AUTH": bool(permission if maintenance else automatic_authorized),
        "LP-SCOPE": scope_ok,
        "LP-SOURCE": source_ok,
        "LP-CI": ci,
        "LP-RULES": queue_rules(client.get(BASE + "rules/branches/main")),
        "LP-DISCUSSION": discussions_clear(client, number),
    }
    if not maintenance:
        values["LP-CANDIDATE"] = bool(
            report["stable_during_collection"]
            and report["head_sha"] == expected_head
            and report["base_sha"] == base_sha
            and report["candidate_decision"] == "eligible"
        )
    now = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    context = {
        "configuration": config,
        "maintenance_authorization": permission,
        "stage": phase,
        "reviewed_head": expected_head,
        "evaluated_sha": target,
        "base_sha": base_sha,
        "candidate_request": report["shadow"]["evaluation"]["request_sha256"]
        if report
        else None,
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
    result = assess(bundle(maintenance), "candidate", subject, observations, now)
    again = client.get(BASE + f"pulls/{number}")
    branch = client.get(BASE + "branches/main")
    require(
        current_pr(again, expected_head)
        and branch
        and branch["commit"]["sha"] == base_sha
        and configuration() == config
        and (
            not maintenance
            or maintenance_authorization(
                client, number, expected_head, base_sha, phase, config
            )
            == permission
        )
        and not client.errors,
        "pilot_state_changed",
    )
    return {
        "schema_version": "lab-pilot-result/v2",
        "repository": REPO,
        "pull_request": number,
        "stage": phase,
        "mode": "maintenance" if maintenance else "automatic",
        "reviewed_head": expected_head,
        "evaluated_sha": target,
        "base_sha": base_sha,
        "configuration_sha256": digest(config),
        "decision": result["decision"],
        "maintenance_authorization": permission,
        "production_readiness": report["readiness_decision"]
        if report
        else "not_assessed",
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
    token = os.environ.get("PILOT_ENQUEUE_TOKEN", "")
    require(bool(token), "repository_app_token_required")
    verify_scope()
    child_env = {
        k: os.environ[k]
        for k in ["PATH", "HOME", "LANG", "XDG_CONFIG_HOME"]
        if k in os.environ
    }
    child_env["GH_TOKEN"] = token
    child = subprocess.run(
        command, env=child_env, capture_output=True, text=True, timeout=60
    )
    require(child.returncode == 0, "github_queue_request_failed")
    return "native_auto_merge_requested"


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
            number = int(match[1])
            pr = g.Client().get(BASE + f"pulls/{number}")
            head = (pr or {}).get("head", {}).get("sha")
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
                "# Repository Gemara pilot\n\n"
                + f"PR #{number}; evaluated `{result['evaluated_sha']}`; stage {args.phase}; decision **{result['decision']}**. Production qualification: **{result['production_readiness']}**.\n\n"
                + "\n".join(
                    f"- {r['id']}: {r['state']} ({r['reason']})"
                    for r in compact["assessments"]
                )
                + "\n"
            )
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with Path(output).open("a") as stream:
                stream.write(
                    "eligible=" + str(result["decision"] == "eligible").lower() + "\n"
                )
        if (
            result["decision"] != "eligible"
            and args.phase == "enroll"
            and not args.execute
            and os.environ.get("PILOT_EXECUTE_REQUESTED") != "true"
        ):
            return 0
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
