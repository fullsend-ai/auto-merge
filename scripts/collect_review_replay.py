#!/usr/bin/env python3
"""Authenticate one owner-selected retained Review; export bounded data only.

This is a replay collector, not current-candidate authorization. Never executes
downloaded code. This GitHub replay is advisory; current-candidate collection is separate.
"""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    return json.loads(raw, object_pairs_hook=unique)


def get(url, token, header="Authorization", maximum=2 * 1024 * 1024):
    headers = {"User-Agent": "gemara-review-replay"}
    if token:
        headers[header] = token
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(
        urllib.request.Request(url, headers=headers), timeout=30
    ) as response:
        raw = response.read(maximum + 1)
    require(len(raw) <= maximum, "response_too_large")
    return raw


def github(binding):
    require(binding["host"] == "github.com", "unsupported_github_host")
    require(
        binding["repository"] == "fullsend-ai/auto-merge"
        and binding["project_id"] == 1383516376,
        "wrong_github_repository",
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gemara-auto-merge"))
    from native_review_artifacts import download
    from review_evidence_retention import extract_record

    api = "https://api.github.com/repos/" + binding["repository"] + "/"
    token = os.environ.get("GH_TOKEN", "")

    def api_get(path):
        return decode(get(api + path, "Bearer " + token if token else ""))

    source = binding["source"]
    require(
        all(
            re.fullmatch(r"[0-9a-f]{40}", source.get(k, ""))
            for k in ["configuration_sha", "fullsend_commit"]
        ),
        "invalid_source_sha",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", source.get("publisher_sha256", "")),
        "invalid_publisher_digest",
    )
    run = api_get("actions/runs/" + str(source["run_id"]))
    require(
        run["id"] == source["run_id"]
        and run["run_attempt"] == 1
        and run["repository"]["id"] == binding["project_id"],
        "wrong_review_run",
    )
    require(
        run["status"] == "completed"
        and run["conclusion"] == "success"
        and run["event"] == "pull_request_target"
        and run["path"] == ".github/workflows/fullsend.yaml",
        "untrusted_review_run",
    )
    # GitHub labels a pull_request_target run with the reviewed PR head;
    # head_sha is NOT the GITHUB_SHA/base commit used for trusted execution.
    require(run["head_sha"] == binding["head_sha"], "wrong_review_run_head")
    references = run.get("referenced_workflows", [])
    require(
        len(references) == 1
        and references[0].get("sha") == source["fullsend_commit"]
        and references[0].get("path")
        == "fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@"
        + source["fullsend_commit"],
        "wrong_review_harness",
    )
    producer_file = api_get(
        "contents/.fullsend/scripts/publish-review-evidence.py?ref="
        + source["configuration_sha"]
    )
    require(
        hashlib.sha256(
            base64.b64decode(producer_file["content"], validate=False)
        ).hexdigest()
        == source["publisher_sha256"],
        "publisher_pin_mismatch",
    )
    artifact = api_get("actions/artifacts/" + str(source["artifact_id"]))
    require(not artifact["expired"], "replay_source_expired")
    require(
        artifact["workflow_run"]["id"] == source["run_id"]
        and artifact["workflow_run"].get("head_sha") == binding["head_sha"]
        and artifact["name"] == "fullsend-review-evidence-1",
        "wrong_review_artifact",
    )
    require(0 < artifact["size_in_bytes"] <= 256 * 1024, "artifact_too_large")
    subject = {
        "repository_id": binding["project_id"],
        "repository": binding["repository"],
        "pull_request": binding["change"],
        "head_sha": binding["head_sha"],
        "base_sha": source["configuration_sha"],
        "configuration_sha": source["configuration_sha"],
    }
    producer = {
        "kind": "fullsend-post-script-lab",
        "fullsend_commit": source["fullsend_commit"],
        "publisher_sha256": source["publisher_sha256"],
        "workflow_path": ".github/workflows/fullsend.yaml",
        "run_id": source["run_id"],
        "run_attempt": 1,
    }
    record = decode(
        extract_record(download(source["artifact_id"]), artifact, subject, producer)
    )
    review = record["review"]
    result = {
        "head_sha": subject["head_sha"],
        "action": review["action"],
        "risk_assessment": review["risk"],
    }
    ledger = {
        "version": 2,
        "action": review["action"],
        "findings": [
            {
                "id": f["id"],
                "severity": f["severity"],
                "category": f["category"],
                "file": None,
            }
            for f in review["findings"]
        ],
        "dispositions": [
            {"id": f["id"], "status": f["status"]} for f in review["findings"]
        ],
    }
    return result, ledger, artifact["digest"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    binding = decode(Path(args.binding).read_bytes())
    require(
        binding["schema_version"] == "review-replay/v1"
        and binding["mode"] == "retained-review-replay",
        "replay_binding_required",
    )
    require(
        re.fullmatch(r"[a-z0-9.-]+", binding["host"])
        and re.fullmatch(r"[0-9a-f]{40}", binding["head_sha"]),
        "invalid_binding",
    )
    require(
        type(binding["maximum_risk"]) is int and 1 <= binding["maximum_risk"] <= 5,
        "invalid_risk_threshold",
    )
    require(binding["forge"] == "github", "unsupported_replay_forge")
    result, ledger, digest = github(binding)
    require(
        isinstance(ledger, dict)
        and ledger.get("version") == 2
        and isinstance(ledger.get("findings"), list),
        "invalid_ledger",
    )
    output = Path(args.output)
    require(not output.exists(), "output_already_exists")
    output.mkdir(mode=0o700, parents=True)
    for name, value in [
        ("result.json", result),
        ("ledger.json", ledger),
        (
            "context.json",
            {
                "mode": "retained-review-replay",
                "forge": binding["forge"],
                "head_sha": binding["head_sha"],
                "maximum_risk": binding["maximum_risk"],
                "archive_digest": digest,
                "authorization": "none",
            },
        ),
    ]:
        (output / name).write_text(json.dumps(value, sort_keys=True) + "\n")
    print(
        "Authenticated retained Review data collected; replay only, no merge authority."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        reason = str(error)
        if not re.fullmatch(r"[a-z0-9_-]{1,80}", reason):
            reason = "replay_collection_failed"
        raise SystemExit(reason)
