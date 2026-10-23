"""Resolve trusted Fullsend config and assess one selected upstream requirement.

This is a GitHub evidence adapter. OSPS supplies the requirement; the existing
Gemara SDK executes the assessment. No credentials are passed to the binary.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

from policy_evaluation import ROOT, assess, digest, load, require, subject

REPO = ROOT.parent
UPSTREAM = ROOT / "upstream/osps-baseline"
CONTROL = "OSPS-QA-03.01"
CONFIGURATION_PATHS = [".fullsend/config.yaml", ".fullsend/config.base.yaml", ".fullsend/bin/fullsend", ".fullsend/local-build.json"]


def configuration():
    binary = REPO / ".fullsend/bin/fullsend"
    lock = load(REPO / ".fullsend/local-build.json")
    require(binary.is_file() and not binary.is_symlink(), "vendored_fullsend_missing")
    require(hashlib.sha256(binary.read_bytes()).hexdigest() == lock["binary_sha256"], "vendored_fullsend_changed")
    child = subprocess.run(
        [str(binary), "auto-merge", "config", "--config-dir", str(REPO / ".fullsend")],
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GOTELEMETRY": "off"},
        capture_output=True, text=True, timeout=15,
    )
    require(child.returncode == 0 and len(child.stdout) < 4096, "auto_merge_configuration_invalid")
    value = json.loads(child.stdout)
    require(set(value) <= {"mode", "policy", "controls"}
            and value.get("mode") in {"off", "shadow", "enforce"}
            and value.get("policy") == "fullsend-default"
            and value.get("controls", []) in [[], [CONTROL]], "auto_merge_configuration_invalid")
    return value


def upstream_bundle():
    lock = load(UPSTREAM / "source.json")
    require(lock["commit"] == "a26a7963f6fd098c1e82829322ec9e1196a4f294"
            and lock["selected_requirement"] == CONTROL, "upstream_source_invalid")
    for name, key in [("OSPS-QA.yaml", "sha256"), ("catalog.json", "projection_sha256"), ("policy.json", "policy_sha256")]:
        p = UPSTREAM / name
        require(not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest() == lock[key], "upstream_source_changed")
    catalog, policy = load(UPSTREAM / "catalog.json"), load(UPSTREAM / "policy.json")
    return {"root_policy": policy["metadata"]["id"], "catalogs": {catalog["metadata"]["id"]: catalog}, "policies": {policy["metadata"]["id"]: policy}}


def checks_value(client, head, phase="enroll"):
    """All observed automated checks must succeed; no automatic bypass.

    Neutral/skipped runs are not pass/fail checks. Required checks remain
    independently enforced by the existing policy. Incomplete API reads hold.
    """
    require(re.fullmatch("[a-f0-9]{40}", head or ""), "upstream_head_invalid")
    base = "repos/fullsend-ai/auto-merge/"
    checks = client.pages(base + f"commits/{head}/check-runs?filter=latest", "check_runs")
    statuses = client.pages(base + f"commits/{head}/statuses")
    if checks is None or statuses is None or client.errors:
        return None, []
    excluded_suite = None
    if phase == "queue":
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        if not re.fullmatch("[1-9][0-9]{0,14}", run_id):
            return None, []
        run = client.get(base + f"actions/runs/{run_id}")
        if not run or run.get("path") != ".github/workflows/gemara-merge-queue.yml" or run.get("event") != "merge_group" or run.get("head_sha") != head or type(run.get("check_suite_id")) is not int:
            return None, []
        excluded_suite = run["check_suite_id"]
    latest = {}
    for row in checks:
        # This assessment cannot require its own result before returning it.
        # GitHub's required queue check still has to complete before merging.
        if excluded_suite is not None and (row.get("check_suite") or {}).get("id") == excluded_suite and (row.get("app") or {}).get("id") == 15368:
            continue
        if row.get("head_sha") != head or type(row.get("id")) is not int:
            return None, []
        if row.get("status") == "completed" and row.get("conclusion") in {"neutral", "skipped"}:
            continue
        app = row.get("app") or {}
        key = (app.get("id"), row.get("name"))
        if row["id"] > latest.get(key, {}).get("id", -1):
            latest[key] = row
    evidence = []
    for row in latest.values():
        conclusion = row.get("conclusion")
        if row.get("status") == "completed" and conclusion in {"neutral", "skipped"}:
            continue
        evidence.append({"kind": "check", "id": row["id"], "passed": row.get("status") == "completed" and conclusion == "success"})
    latest_statuses = {}
    for row in statuses:
        if type(row.get("id")) is not int or not isinstance(row.get("context"), str):
            return None, []
        key = row["context"]
        if row["id"] > latest_statuses.get(key, {}).get("id", -1):
            latest_statuses[key] = row
    evidence += [{"kind": "status", "id": row["id"], "passed": row.get("state") == "success"} for row in latest_statuses.values()]
    return (all(row["passed"] for row in evidence) if evidence else None), evidence


def evaluate(client, head, base, instant, phase="enroll"):
    cfg = configuration()
    result = {"configuration": cfg, "configuration_sha256": digest(cfg), "decision": "hold", "would_allow": False, "assessments": [], "mutation_permitted": False}
    if cfg["mode"] == "off":
        result["reason"] = "mode_off"
        return result
    eligible = True
    if CONTROL in cfg.get("controls", []):
        bundle = upstream_bundle()
        who = subject(repository="fullsend-ai/auto-merge", configuration=digest(cfg), candidate=True)
        who.update(head_sha=head, base_sha=base)
        value, checks = checks_value(client, head, phase)
        observations = {"OSPS-QA-03": {"subject_sha256": digest(who), "collected_at": instant, "trusted_source": not client.errors, "value": value}}
        evaluated = assess(bundle, "maturity-2", who, observations, instant)
        result.update(evaluation=evaluated, assessments=evaluated["assessments"], checks=checks,
                      source={"repository": "ossf/security-baseline", "release": "v2026.08.28", "requirement": CONTROL})
        eligible = evaluated["decision"] == "eligible"
    result["would_allow"] = eligible
    result["decision"] = "eligible" if eligible and cfg["mode"] == "enforce" else "hold"
    result["reason"] = "shadow_no_write" if cfg["mode"] == "shadow" else "evaluated"
    return result


def main():
    """Observe a selected control without requiring or granting merge authority."""
    import argparse
    from datetime import datetime, timezone
    import github_pr_evidence as forge
    from policy_evaluation import new_output

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    require(0 < args.pr < 1000000, "upstream_pr_invalid")
    client = forge.Client()
    endpoint = f"repos/fullsend-ai/auto-merge/pulls/{args.pr}"
    pr = client.get(endpoint)
    require(pr and pr.get("base", {}).get("ref") == "main"
            and pr.get("base", {}).get("repo", {}).get("full_name") == "fullsend-ai/auto-merge", "upstream_subject_invalid")
    head, base = pr["head"]["sha"], pr["base"]["sha"]
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = evaluate(client, head, base, instant)
    current = client.get(endpoint)
    require(current and current["head"]["sha"] == head and current["base"]["sha"] == base and not client.errors, "upstream_subject_changed")
    result.update(pr=args.pr, head_sha=head, base_sha=base, collected_at=instant)
    out = new_output("configured")
    (out / "configured-policy.json").write_text(json.dumps(result, indent=2) + "\n")
    if "evaluation" in result:
        (out / "upstream-evaluation-log.json").write_text(json.dumps(result["evaluation"]["evaluation_log"], indent=2) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write("\n\n# Selected upstream control\n\n")
            stream.write(f"PR #{args.pr} · `{head}` · mode **{result['configuration']['mode']}**\n\n")
            for row in result["assessments"]:
                stream.write(f"- {row['requirement']}: **{row['state']}** ({row['reason']})\n")
            stream.write("\nRead-only observation. This result grants no merge authority; the existing owner grant and protected writer remain separate.\n")
    print(json.dumps({"pr": args.pr, "mode": result["configuration"]["mode"], "assessments": result["assessments"], "mutation_permitted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
