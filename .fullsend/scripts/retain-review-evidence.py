#!/usr/bin/env python3
"""Publish the existing bounded member; never execute or retain other output."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    root = Path(os.environ["GITHUB_WORKSPACE"])
    sys.path.insert(0, str(root / "gemara-auto-merge"))
    from native_review_artifacts import BASE, download
    from policy_evaluation import load, require
    from review_evidence_retention import MAX_ARCHIVE, MEMBER, extract_record

    require(
        os.environ["GITHUB_REPOSITORY"] == "fullsend-ai/auto-merge",
        "retention_wrong_repository",
    )
    require(
        os.environ["GITHUB_REPOSITORY_ID"] == "1383516376", "retention_wrong_repository"
    )
    require(
        os.environ["GITHUB_EVENT_NAME"] == "pull_request_target",
        "retention_wrong_event",
    )
    run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    require(
        all(re.fullmatch(r"[1-9][0-9]{0,14}", value) for value in [run_id, attempt]),
        "retention_invalid_run",
    )
    event = load(Path(os.environ["GITHUB_EVENT_PATH"]))
    pr = event["pull_request"]
    configuration = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        env={
            "PATH": "/usr/bin:/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        },
        text=True,
        timeout=10,
    ).strip()
    require(configuration == pr["base"]["sha"], "retention_wrong_configuration")
    for side in ["base", "head"]:
        require(pr[side]["repo"]["id"] == 1383516376, "retention_wrong_repository")
    producer = load(root / ".fullsend/review-evidence-producer.json")
    subject = {
        "repository_id": 1383516376,
        "repository": "fullsend-ai/auto-merge",
        "pull_request": pr["number"],
        "head_sha": pr["head"]["sha"],
        "base_sha": configuration,
        "configuration_sha": configuration,
    }
    identity = {
        "kind": "fullsend-post-script-lab",
        "fullsend_commit": producer["source_commit"],
        "publisher_sha256": producer["publisher_sha256"],
        "workflow_path": ".github/workflows/fullsend.yaml",
        "run_id": int(run_id),
        "run_attempt": int(attempt),
    }
    child = subprocess.run(
        ["gh", "api", BASE + f"actions/runs/{run_id}/artifacts?per_page=100"],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    require(len(child.stdout) <= 1024 * 1024, "retention_metadata_oversized")
    rows = json.loads(child.stdout)["artifacts"]
    require(len(rows) < 100, "retention_metadata_incomplete")
    rows = [row for row in rows if row.get("name") == "fullsend-review"]
    if not rows:
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("present=false\n")
        print("No routed Review artifact in this event; no evidence published.")
        return
    require(len(rows) == 1 and not rows[0]["expired"], "retention_artifact_ambiguous")
    metadata = rows[0]
    require(
        type(metadata["size_in_bytes"]) is int
        and 0 < metadata["size_in_bytes"] <= MAX_ARCHIVE,
        "retention_archive_oversized",
    )
    raw = extract_record(
        download(metadata["id"], MAX_ARCHIVE), metadata, subject, identity
    )
    destination = root / "output"
    require(not destination.is_symlink(), "retention_symlink_output")
    destination.mkdir(exist_ok=True)
    path = destination / MEMBER
    require(not path.exists() and not path.is_symlink(), "retention_existing_output")
    path.write_bytes(raw)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("present=true\n")
    print("Retained validated same-run v2 record; other output was not extracted.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Bounded Review evidence retention failed; no evidence accepted."
        )
