#!/usr/bin/env python3
"""Trusted host publication after a successful native Review post, never PR code."""

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request


def main():
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    if (
        os.environ["GITHUB_REPOSITORY"] != "fullsend-ai/auto-merge"
        or os.environ["GITHUB_REPOSITORY_ID"] != "1383516376"
    ):
        raise ValueError("wrong_repository")
    sys.path.insert(0, str(workspace / "gemara-auto-merge"))
    from fullsend_review_evidence import ledger_clear, unique_object

    projection = sys.stdin.read(128 * 1024 + 1)
    if len(projection) > 128 * 1024:
        raise ValueError("oversized_projection")
    ledger_clear(base64.b64encode(projection.encode()).decode())
    ledger = json.loads(projection, object_pairs_hook=unique_object)
    result_path = Path(sys.argv[1])
    if result_path.is_symlink() or result_path.stat().st_size > 1024 * 1024:
        raise ValueError("invalid_result")
    result = json.loads(result_path.read_text(), object_pairs_hook=unique_object)
    url = os.environ["PR_URL"]
    match = re.fullmatch(
        r"https://github.com/fullsend-ai/auto-merge/pull/([1-9][0-9]{0,5})", url
    )
    if not match:
        raise ValueError("invalid_pr")
    headers = {
        "Authorization": "Bearer " + os.environ["REVIEW_TOKEN"],
        "Accept": "application/vnd.github+json",
        "User-Agent": "fullsend-review-evidence-lab",
    }

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            raise ValueError("redirect_refused")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(
        urllib.request.Request(
            "https://api.github.com/repos/fullsend-ai/auto-merge/pulls/" + match[1],
            headers=headers,
        ),
        timeout=20,
    ) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("oversized_pr")
    pr = json.loads(raw)
    clean = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    configuration = subprocess.check_output(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        env=clean,
        text=True,
        timeout=10,
    ).strip()
    if (
        pr["head"]["sha"] != result.get("head_sha")
        or pr["base"]["sha"] != configuration
        or pr["base"]["repo"]["full_name"] != "fullsend-ai/auto-merge"
    ):
        raise ValueError("review_context_changed")
    binary = workspace / ".fullsend/bin/fullsend"
    build = json.loads((workspace / ".fullsend/evidence-build.json").read_text())
    if (
        binary.is_symlink()
        or hashlib.sha256(binary.read_bytes()).hexdigest() != build["binary_sha256"]
    ):
        raise ValueError("binary_mismatch")
    dispositions = {x["id"]: x["status"] for x in ledger.get("dispositions", [])}
    risk = result.get("risk_assessment")
    risk = (
        {"score": risk.get("score"), "level": risk.get("level")}
        if isinstance(risk, dict) and "degraded" not in risk
        else None
    )
    value = {
        "subject": {
            "repository_id": 1383516376,
            "repository": "fullsend-ai/auto-merge",
            "pull_request": int(match[1]),
            "head_sha": result["head_sha"],
            "base_sha": pr["base"]["sha"],
            "configuration_sha": configuration,
        },
        "producer": {
            "kind": "fullsend-host-lab",
            "fullsend_commit": build["source_commit"],
            "overlay_sha256": build["overlay_sha256"],
            "workflow_path": ".github/workflows/fullsend.yaml",
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        },
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completion": "completed",
        "review": {
            "action": ledger["action"],
            "findings": [
                {
                    "id": x["id"],
                    "severity": x["severity"],
                    "category": x["category"],
                    "status": dispositions.get(x["id"], "open"),
                }
                for x in ledger["findings"]
            ],
            "risk": risk,
        },
    }
    child = subprocess.run(
        [str(binary), "review-evidence-lab"],
        input=json.dumps(value),
        text=True,
        capture_output=True,
        env=clean,
        timeout=30,
    )
    if child.returncode or len(child.stdout) > 128 * 1024:
        raise ValueError("native_publication_failed")
    destination = workspace / "output/fullsend-review-evidence.json"
    if destination.parent.is_symlink():
        raise ValueError("symlink_publication_directory")
    destination.parent.mkdir(exist_ok=True)
    if destination.is_symlink():
        raise ValueError("symlink_publication")
    destination.write_text(child.stdout)
    print(
        "Native Fullsend Review evidence published; authentication requires the completed Actions run."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Native Review evidence publication failed; no partial record is accepted."
        )
