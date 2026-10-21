#!/usr/bin/env python3
"""Owner-only setup: audit hidden bypass actors and publish a bounded version record.

Run locally with an authenticated repository-admin gh CLI, after protections are
restored. This does not change protections or upload the owner's credential.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gemara-auto-merge"))
from shared_gate import ruleset_public_state, settings
from policy_evaluation import digest, require

REPO = "fullsend-ai/auto-merge"
ENVIRONMENT = "gemara-policy-reader"


def api(path):
    result = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, timeout=30
    )
    require(result.returncode == 0, "owner_api_unavailable")
    return json.loads(result.stdout)


def audit():
    require(
        api("repos/" + REPO)["permissions"]["admin"] is True,
        "repository_admin_required",
    )
    rows = []
    for page in range(1, 11):
        batch = api(f"repos/{REPO}/rulesets?per_page=100&page={page}")
        require(isinstance(batch, list), "ruleset_list_invalid")
        rows.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError("ruleset_list_incomplete")
    require(
        bool(rows) and len({r["id"] for r in rows}) == len(rows), "ruleset_list_invalid"
    )
    rules = [api(f"repos/{REPO}/rulesets/{row['id']}") for row in rows]
    for rule in rules:
        require(
            isinstance(rule.get("bypass_actors"), list),
            "owner_bypass_visibility_required",
        )
        require(
            rule["enforcement"] != "active" or rule["bypass_actors"] == [],
            "active_bypass_prevents_audit",
        )
    latest = max(
        datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) for r in rules
    )
    require(latest <= datetime.now(timezone.utc), "future_ruleset_timestamp")
    # Leave the provider's timestamp bucket before making this owner assertion.
    while datetime.now(timezone.utc) <= latest + timedelta(seconds=2):
        time.sleep(0.25)
    require(
        rules == [api(f"repos/{REPO}/rulesets/{row['id']}") for row in rows],
        "rules_changed_during_audit",
    )
    result = dict(
        schema_version="github-ruleset-audit/v1",
        repository=REPO,
        repository_id=1383516376,
        audited_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=settings()["binding"]["owner_grant_expires_at"],
        rulesets=[
            dict(
                id=r["id"],
                bypass_disabled=True,
                public_state_sha256=digest(ruleset_public_state(r)),
            )
            for r in rules
        ],
    )
    base = f"repos/{REPO}/environments/{ENVIRONMENT}"
    require(
        api(base)["deployment_branch_policy"]
        == {"protected_branches": False, "custom_branch_policies": True},
        "main_only_environment_required",
    )
    policies = api(base + "/deployment-branch-policies")["branch_policies"]
    require(
        len(policies) == 1
        and policies[0]["name"] == "main"
        and policies[0]["type"] == "branch",
        "main_only_environment_required",
    )
    response = subprocess.run(
        [
            "gh",
            "variable",
            "set",
            "GEMARA_RULESET_AUDIT",
            "-R",
            REPO,
            "--env",
            ENVIRONMENT,
        ],
        input=json.dumps(result),
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(response.returncode == 0, "owner_audit_publication_failed")
    readback = subprocess.run(
        [
            "gh",
            "variable",
            "list",
            "-R",
            REPO,
            "--env",
            ENVIRONMENT,
            "--json",
            "name,value",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(readback.returncode == 0, "owner_audit_readback_failed")
    records = json.loads(readback.stdout)
    actual = [r for r in records if r["name"] == "GEMARA_RULESET_AUDIT"]
    require(
        len(actual) == 1 and json.loads(actual[0]["value"]) == result,
        "owner_audit_readback_failed",
    )
    print(
        "Owner ruleset audit published and verified; no active bypass; existing grant expiry preserved."
    )


if __name__ == "__main__":
    try:
        audit()
    except Exception:
        raise SystemExit(
            "Owner ruleset audit refused; check admin access, bypasses and environment restrictions."
        )
