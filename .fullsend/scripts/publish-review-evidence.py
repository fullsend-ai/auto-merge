#!/usr/bin/env python3
"""Trusted host publication after a successful native Review post, never PR code."""

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

SHARED_MODULE = "github.com/ascerra/fullsend-gemara-integration/cmd/gemara-owner@a73a3d88471f1fe5e947b11936430d7b298091f2"


def project_review(result_path, projection, head):
    """Run the immutable public helper without forge or inherited credentials."""
    go = shutil.which("go")
    if not go:
        raise ValueError("shared_helper_go_unavailable")
    with tempfile.TemporaryDirectory(prefix="gemara-review-projection-") as directory:
        ledger = Path(directory) / "ledger.json"
        ledger.write_text(projection)
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": directory,
            "GOPATH": directory + "/gopath",
            "GOCACHE": directory + "/cache",
            "GOTOOLCHAIN": "local",
            "GOTELEMETRY": "off",
            "GOPROXY": "https://proxy.golang.org",
            "GOSUMDB": "sum.golang.org",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
        }
        result = subprocess.run(
            [go, "run", SHARED_MODULE, "project-review", "--result",
             str(result_path.resolve()), "--ledger", str(ledger), "--head", head],
            cwd=directory, env=env, capture_output=True, text=True, timeout=180,
        )
        if result.returncode or len(result.stdout) > 128 * 1024:
            raise ValueError("shared_review_projection_failed")
        value = json.loads(result.stdout)
        if (value.get("schema_version") != "review-projection/v1"
            or value.get("head_sha") != head
            or value.get("authorization") != "none"
            or value.get("mutation_permitted") is not False):
            raise ValueError("invalid_shared_projection")
        return value["review"]


def main():
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    if (
        os.environ["GITHUB_REPOSITORY"] != "fullsend-ai/auto-merge"
        or os.environ["GITHUB_REPOSITORY_ID"] != "1383516376"
    ):
        raise ValueError("wrong_repository")
    sys.path.insert(0, str(workspace / "gemara-auto-merge"))
    from fullsend_review_evidence import ledger_clear, unique_object
    from policy_evaluation import load
    from review_evidence_contract import encode_post_script

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
    producer = load(workspace / ".fullsend/review-evidence-producer.json")
    publisher = Path(__file__).resolve()
    publisher_sha256 = hashlib.sha256(publisher.read_bytes()).hexdigest()
    if (
        producer.get("schema_version") != "review-post-script-producer/v1"
        or producer.get("publisher_sha256") != publisher_sha256
    ):
        raise ValueError("publisher_source_mismatch")
    dispositions = {x["id"]: x["status"] for x in ledger.get("dispositions", [])}
    shared = project_review(result_path, projection, result["head_sha"])
    expected_findings = [
        {"id": x["id"], "status": dispositions.get(x["id"], "open")}
        for x in ledger["findings"]
    ]
    if (shared.get("completed") is not True
        or shared.get("action") != ledger["action"]
        or shared.get("findings") != expected_findings):
        raise ValueError("shared_projection_conflict")
    risk = result.get("risk_assessment")
    risk = (
        {"score": shared["risk_score"], "level": risk.get("level")}
        if shared.get("risk_score") is not None and isinstance(risk, dict)
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
            "kind": "fullsend-post-script-lab",
            "fullsend_commit": producer["source_commit"],
            "publisher_sha256": publisher_sha256,
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
    encoded = encode_post_script(value)
    destination = workspace / "output/fullsend-review-evidence.json"
    if destination.parent.is_symlink():
        raise ValueError("symlink_publication_directory")
    destination.parent.mkdir(exist_ok=True)
    if destination.is_symlink():
        raise ValueError("symlink_publication")
    destination.write_text(encoded)
    print(
        "Post-script Review evidence v2 published; authentication requires the completed Actions run."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Native Review evidence publication failed; no partial record is accepted."
        )
