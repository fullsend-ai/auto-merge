"""Trusted GitHub adapter and receipt verifier; never executes shared code with a writer token."""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile

import github_pr_evidence as g
import native_review_artifacts as native
from policy_evaluation import ROOT, digest, load, require, utc

BASE = "repos/fullsend-ai/auto-merge/"
CONFIG = ROOT / "config/shared-gate.json"


def settings():
    c = load(CONFIG)
    require(
        c["schema_version"] == "shared-merge-gate/v1" and c["required"] is True,
        "shared_gate_required",
    )
    require(
        c["tool"]["module"] == "github.com/ascerra/fullsend-gemara-integration"
        and re.fullmatch("[a-f0-9]{40}", c["tool"]["commit"]),
        "shared_tool_invalid",
    )
    return c


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def binding_digest(binding):
    # Match Go's declared struct field order, including the nested Identity.
    keys = [
        "schema_version",
        "identity",
        "allowed_paths",
        "governed_paths",
        "required_checks",
        "review_workflow",
        "maximum_risk",
        "maximum_evidence_age_seconds",
        "owner_grant_enabled",
        "owner_grant_expires_at",
    ]
    b = {k: binding[k] for k in keys}
    b["identity"] = {
        k: b["identity"][k]
        for k in ["forge", "host", "project_id", "repository", "target_branch"]
    }
    return hashlib.sha256(json.dumps(b, separators=(",", ":")).encode()).hexdigest()


def artifact(client, run, name, expected_files):
    rows = client.pages(BASE + f"actions/runs/{run['id']}/artifacts", "artifacts")
    matches = [a for a in rows or [] if a.get("name") == name]
    require(len(matches) == 1, "shared_artifact_missing_or_ambiguous")
    a = matches[0]
    require(
        a.get("expired") is False and 0 < a.get("size_in_bytes", 0) <= 256 * 1024,
        "shared_artifact_invalid",
    )
    subject = a.get("workflow_run") or {}
    require(
        subject.get("id") == run["id"] and subject.get("head_sha") == run["head_sha"],
        "shared_artifact_wrong_run",
    )
    raw = native.download(a["id"])
    require(
        a.get("digest") == "sha256:" + hashlib.sha256(raw).hexdigest(),
        "shared_artifact_digest_mismatch",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(
            set(archive.namelist()) == set(expected_files)
            and len(archive.infolist()) == len(expected_files),
            "shared_artifact_layout_invalid",
        )
        require(
            all(
                x.file_size <= 128 * 1024
                and x.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                for x in archive.infolist()
            ),
            "shared_artifact_oversized",
        )
        return {name: json.loads(archive.read(name)) for name in expected_files}


def main_run(run, source):
    return bool(
        run
        and run.get("repository", {}).get("full_name") == g.REPOSITORY
        and run.get("head_repository", {}).get("full_name") == g.REPOSITORY
        and run.get("event") in {"workflow_run", "workflow_dispatch"}
        and run.get("path") == ".github/workflows/gemara-auto-merge.yml"
        and run.get("head_branch") == "main"
        and run.get("head_sha") == source
        and type(run.get("run_attempt")) is int
    )


def job_succeeded(client, run, name):
    jobs = client.pages(
        BASE + f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs"
    )
    selected = [
        j
        for j in jobs or []
        if j.get("name") == name or j.get("name", "").endswith(" / " + name)
    ]
    return (
        len(selected) == 1
        and selected[0].get("status") == "completed"
        and selected[0].get("conclusion") == "success"
    )


def quality_snapshot(client, source):
    runs = client.pages(
        BASE + "actions/workflows/gemara-auto-merge.yml/runs?branch=main",
        "workflow_runs",
    )
    for run in sorted(runs or [], key=lambda r: r["id"], reverse=True)[:10]:
        if main_run(run, source) and job_succeeded(
            client, run, "Collect quality aggregate"
        ):
            data = artifact(
                client,
                run,
                f"shared-quality-{run['run_attempt']}",
                ["quality.json", "quality-context.json"],
            )
            ctx = data["quality-context.json"]
            require(
                ctx
                == {
                    "source_sha": source,
                    "run_id": str(run["id"]),
                    "attempt": str(run["run_attempt"]),
                    "config_sha256": digest(settings()),
                },
                "shared_quality_context_mismatch",
            )
            return data["quality.json"]
    require(False, "shared_quality_snapshot_missing")


def collect(number, head, phase, output, client=None):
    import authorize_auto_merge as pilot

    client = client or g.Client()
    c = settings()
    source = os.environ.get("PILOT_SOURCE_SHA", "")
    require(re.fullmatch("[a-f0-9]{40}", source), "shared_source_missing")
    pr = client.get(BASE + f"pulls/{number}")
    branch = client.get(BASE + "branches/main")
    require(
        pilot.current_pr(pr, head)
        and branch["commit"]["sha"] == source
        and pilot.trusted_source(
            client,
            source,
            phase,
            os.environ.get("PILOT_GROUP_SHA") if phase == "queue" else None,
        ),
        "shared_untrusted_execution",
    )
    report = g.observe(number, client)
    require(
        report["stable_during_collection"]
        and report["head_sha"] == head
        and report["base_sha"] == source,
        "shared_candidate_changed",
    )
    proof = report.get("native_review_evidence") or {}
    values = proof.get("values", {})
    files = client.pages(BASE + f"pulls/{number}/files")
    require(
        files is not None and len(files) == pr["changed_files"],
        "shared_files_incomplete",
    )
    tree = pilot.tree(client, head)
    checks = client.pages(
        BASE + f"commits/{head}/check-runs?filter=latest", "check_runs"
    )
    require(checks is not None, "shared_checks_missing")
    subject = {
        "identity": c["binding"]["identity"],
        "change": number,
        "head_sha": head,
        "target_sha": source,
        "policy_sha256": c["candidate_policy_sha256"],
        "binding_sha256": binding_digest(c["binding"]),
    }
    artifact_digest = ""
    if proof.get("reason") == "contract_verified":
        require(
            proof["subject"]["head_sha"] == head
            and proof["subject"]["base_sha"] == pr["base"]["sha"],
            "shared_review_wrong_subject",
        )
        a = client.get(BASE + f"actions/artifacts/{proof['artifact_id']}")
        artifact_digest = (a or {}).get("digest", "").removeprefix("sha256:")
    normalized_checks = []
    for name in c["binding"]["required_checks"]:
        for check in checks:
            if (
                check.get("name") == name
                and (check.get("app") or {}).get("id") == 15368
            ):
                normalized_checks.append(
                    {
                        "name": name,
                        "head_sha": check.get("head_sha", ""),
                        "status": (
                            "success"
                            if check.get("status") == "completed"
                            and check.get("conclusion") == "success"
                            else "not_successful"
                        ),
                    }
                )
    rules = client.get(BASE + "rules/branches/main")
    rulesets = client.get(BASE + "rulesets")
    require(isinstance(rulesets, list), "shared_rulesets_missing")
    bypass = False
    for row in rulesets:
        rule = client.get(BASE + f"rulesets/{row['id']}")
        require(
            isinstance(rule, dict) and isinstance(rule.get("bypass_actors"), list),
            "shared_ruleset_unavailable",
        )
        bypass = bypass or bool(
            rule["enforcement"] == "active" and rule["bypass_actors"]
        )
    review_valid = (
        proof.get("reason") == "contract_verified" and values.get("AM-REVIEW") is True
    )
    e = {
        "source_kind": "collector-observation",
        "subject": subject,
        "collected_at": now(),
        "open": pr["state"] == "open",
        "draft": pr.get("draft") is not False,
        "files": [
            {
                "path": f["filename"],
                "kind": f.get("status", "unknown"),
                "mode": tree.get(f["filename"], ("", "", ""))[1],
                **(
                    {"previous_path": f["previous_filename"]}
                    if "previous_filename" in f
                    else {}
                ),
            }
            for f in files
        ],
        "review": {
            "completed": review_valid,
            "action": "approve" if review_valid else "unknown",
            "risk_score": values.get("AM-RISK"),
            "findings": (
                []
                if values.get("AM-FINDINGS") is True
                else [{"id": "unresolved_or_unknown", "status": "open"}]
            ),
        },
        "checks": normalized_checks,
        "publication": {
            "workflow": c["binding"]["review_workflow"] if review_valid else "",
            "run_id": str(proof.get("run_id", "")),
            "attempt": proof.get("run_attempt", 0),
            "subject": subject,
            "artifact_sha256": artifact_digest,
        },
        "protections": {
            "protected_target": branch.get("protected") is True,
            "required_policy_gate": pilot.queue_rules(rules),
            "discussions_resolved": pilot.discussions_clear(client, number),
            "bypass_enabled": bypass,
            "merge_mechanism": "merge-queue",
        },
    }
    require(
        pilot.current_pr(client.get(BASE + f"pulls/{number}"), head)
        and client.get(BASE + "branches/main")["commit"]["sha"] == source
        and not client.errors,
        "shared_candidate_changed",
    )
    out = Path(output)
    out.mkdir(mode=0o700)
    context = {
        "repository": g.REPOSITORY,
        "pr": number,
        "head_sha": head,
        "source_sha": source,
        "phase": phase,
        "evaluated_sha": (
            os.environ.get("PILOT_GROUP_SHA", head) if phase == "queue" else head
        ),
        "run_id": os.environ["GITHUB_RUN_ID"],
        "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "config_sha256": digest(c),
        "collected_at": e["collected_at"],
    }
    for name, data in [
        ("candidate.json", e),
        ("context.json", context),
        ("config.json", c),
    ]:
        (out / name).write_text(json.dumps(data))
    if phase == "queue":
        (out / "quality.json").write_text(json.dumps(quality_snapshot(client, source)))


def verify_assessment(client, number, head, base, phase, target=None):
    c = settings()
    rid = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(
        re.fullmatch("[1-9][0-9]{0,14}", rid)
        and re.fullmatch("[1-9][0-9]{0,5}", attempt),
        "shared_receipt_run_missing",
    )
    run = client.get(BASE + f"actions/runs/{rid}")
    expected_path = (
        ".github/workflows/gemara-auto-merge.yml"
        if phase == "enroll"
        else ".github/workflows/gemara-merge-queue.yml"
    )
    require(
        run
        and run.get("path") == expected_path
        and run.get("repository", {}).get("full_name") == g.REPOSITORY
        and run.get("head_sha") == (target if phase == "queue" else base)
        and run.get("run_attempt") == int(attempt)
        and run.get("event")
        in (
            {"merge_group"}
            if phase == "queue"
            else {"workflow_run", "workflow_dispatch"}
        ),
        "shared_receipt_untrusted_run",
    )
    require(
        job_succeeded(client, run, "Assess shared merge requirements"),
        "shared_assessment_job_not_successful",
    )
    files = artifact(
        client,
        run,
        f"shared-gate-assessment-{attempt}",
        ["receipt.json", "assessment.json"],
    )
    receipt, assessment = files["receipt.json"], files["assessment.json"]
    ctx = receipt["context"]
    require(
        ctx
        == dict(
            repository=g.REPOSITORY,
            pr=number,
            head_sha=head,
            source_sha=base,
            phase=phase,
            evaluated_sha=target or head,
            run_id=rid,
            attempt=attempt,
            config_sha256=digest(c),
            collected_at=ctx.get("collected_at"),
        ),
        "shared_receipt_subject_mismatch",
    )
    instant = datetime.now(timezone.utc)
    age = (instant - utc(ctx["collected_at"])).total_seconds()
    require(
        0 <= age <= c["binding"]["maximum_evidence_age_seconds"],
        "shared_candidate_receipt_expired",
    )
    quality = receipt["quality"]
    q = c["judge_policy"]
    require(
        0
        <= (instant - utc(quality["collected_at"])).total_seconds()
        <= q["maximum_snapshot_age_seconds"]
        and 0
        <= (instant - utc(quality["latest_score_at"])).total_seconds()
        <= q["maximum_score_age_seconds"],
        "shared_quality_receipt_expired",
    )
    require(
        receipt["assessment_sha256"] == digest(assessment)
        and receipt["quality_sha256"] == digest(quality),
        "shared_receipt_digest_mismatch",
    )
    require(
        assessment["schema_version"] == "candidate-assessment/v1"
        and assessment["authorization"] == "none"
        and assessment["mutation_permitted"] is False,
        "shared_assessment_invalid",
    )
    candidate, judge = assessment["candidate"], assessment["quality"]
    require(
        candidate["subject"]["head_sha"] == head
        and candidate["subject"]["target_sha"] == base
        and candidate["subject"]["change"] == number
        and candidate["binding_sha256"] == binding_digest(c["binding"])
        and candidate["policy_sha256"] == c["candidate_policy_sha256"],
        "shared_report_subject_mismatch",
    )
    expected_subject = dict(
        identity=c["binding"]["identity"],
        change=number,
        head_sha=head,
        target_sha=base,
        policy_sha256=c["candidate_policy_sha256"],
        binding_sha256=binding_digest(c["binding"]),
    )
    require(
        candidate["subject"] == expected_subject
        and candidate["engine"] == "gemara"
        and candidate["evidence_kind"] == "collector-observation"
        and candidate["authorization"] == "none"
        and candidate["mutation_permitted"] is False
        and candidate["catalog_sha256"] == c["candidate_catalog_sha256"],
        "shared_candidate_report_invalid",
    )
    rows = candidate["assessments"]
    require(
        len(rows) == 5
        and {r["id"] for r in rows}
        == {
            "OWNER-SCOPE",
            "REVIEW-CLEAR",
            "CHECKS-PASS",
            "EVIDENCE-CURRENT",
            "PROTECTIONS-ACTIVE",
        },
        "shared_requirements_incomplete",
    )
    require(
        candidate["decision"]
        == ("eligible" if all(r["state"] == "passed" for r in rows) else "hold"),
        "shared_candidate_decision_conflict",
    )
    require(
        judge["schema_version"] == "judge-check/v1"
        and judge["authorization"] == "none"
        and judge["mutation_permitted"] is False
        and judge["minimum_basis_points"] == q["minimum_basis_points"]
        and judge["passed"] == quality["passed"]
        and judge["total"] == quality["total"],
        "shared_quality_report_invalid",
    )
    require(
        judge["decision"] == ("eligible" if judge["state"] == "passed" else "hold"),
        "shared_quality_decision_conflict",
    )
    passed = candidate["decision"] == "eligible" and judge["decision"] == "eligible"
    require(
        assessment["decision"] == ("eligible" if passed else "hold"),
        "shared_decision_conflict",
    )
    require(
        client.get(BASE + f"actions/runs/{rid}") == run and not client.errors,
        "shared_receipt_api_error",
    )
    return assessment


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["enroll", "queue"], required=True)
    p.add_argument("--pr", type=int)
    p.add_argument("--head")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    if a.phase == "queue":
        import authorize_auto_merge as pilot

        match = pilot.GROUP_REF.fullmatch(os.environ.get("PILOT_GROUP_REF", ""))
        require(match is not None, "shared_group_invalid")
        a.pr = int(match[1])
        a.head = g.Client().get(BASE + f"pulls/{a.pr}")["head"]["sha"]
    collect(a.pr, a.head, a.phase, a.output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Shared candidate collection held; no merge authorization.")
