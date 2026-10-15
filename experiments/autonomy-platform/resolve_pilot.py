#!/usr/bin/env python3
"""Resolve a PR hint from forge-owned events; hints never authorize a merge."""

import base64
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

import github_observe as g
from fullsend_evidence import RISK_RECEIPT, current_section, producer, unique_object


def valid_pr(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,5}", value)


def receipt_hint(comment, run_id):
    if not producer(comment):
        return None
    matches = RISK_RECEIPT.findall(current_section(comment.get("body")))
    if len(matches) != 1 or len(matches[0]) > 2048:
        return None
    try:
        data = json.loads(
            base64.b64decode(matches[0], validate=True), object_pairs_hook=unique_object
        )
        if type(data.get("run_id")) is not int or data["run_id"] != run_id:
            return None
        match = re.fullmatch(
            r"https://api.github.com/repos/fullsend-ai/auto-merge/issues/([1-9][0-9]{0,5})",
            comment.get("issue_url", ""),
        )
        return int(match[1]) if match else None
    except Exception:
        return None


def resolve(event_name, event, client):
    if event_name == "workflow_dispatch":
        value = (event.get("inputs") or {}).get("pr")
        number = int(value) if valid_pr(value) else None
        expected = (event.get("inputs") or {}).get("head")
    elif event_name == "workflow_run":
        run = event.get("workflow_run") or {}
        if (
            run.get("repository", {}).get("full_name") != g.REPOSITORY
            or run.get("event")
            not in {"pull_request", "pull_request_target", "issue_comment"}
            or run.get("name") not in {"CI", "fullsend"}
        ):
            return None
        numbers = {
            p.get("number")
            for p in run.get("pull_requests", [])
            if type(p.get("number")) is int
        }
        if not numbers and run.get("name") == "fullsend" and type(run.get("id")) is int:
            since = run.get("created_at")
            if not isinstance(since, str) or not re.fullmatch(r"[0-9T:Z-]{20}", since):
                return None
            data = client.get(
                "repos/"
                + g.REPOSITORY
                + "/issues/comments?per_page=100&since="
                + quote(since, safe="")
            )
            if not isinstance(data, list) or len(data) >= 100:
                return None
            numbers = {
                hint
                for row in data
                if (hint := receipt_hint(row, run["id"])) is not None
            }
        if len(numbers) != 1:
            return None
        number = numbers.pop()
        expected = None
    else:
        return None
    if type(number) is not int or not 0 < number < 1000000:
        return None
    pr = client.get("repos/" + g.REPOSITORY + f"/pulls/{number}")
    if not pr or pr.get("state") != "open" or pr.get("draft") is not False:
        return None
    if (
        pr.get("head", {}).get("repo", {}).get("full_name") != g.REPOSITORY
        or pr.get("base", {}).get("repo", {}).get("full_name") != g.REPOSITORY
        or pr.get("base", {}).get("ref") != "main"
    ):
        return None
    head = pr.get("head", {}).get("sha")
    if (
        not isinstance(head, str)
        or not re.fullmatch("[0-9a-f]{40}", head)
        or (expected is not None and expected != head)
    ):
        return None
    return {"pr": number, "head": head}


def main():
    try:
        raw = Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError()
        client = g.Client()
        target = resolve(os.environ.get("GITHUB_EVENT_NAME"), json.loads(raw), client)
        target = target if not client.errors else None
        values = (
            {"ready": "true", "pr": str(target["pr"]), "head": target["head"]}
            if target
            else {"ready": "false"}
        )
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            stream.write("".join(f"{k}={v}\n" for k, v in values.items()))
        print(json.dumps({"candidate_resolved": bool(target), **(target or {})}))
        return 0
    except Exception:
        print("Candidate resolution failed closed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
