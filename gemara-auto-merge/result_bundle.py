"""Publish only normalized evaluation data, never raw forge or model responses."""

from pathlib import Path
import hashlib
import json
import os
import re

from policy_evaluation import ROOT, digest, load, new_output, require, source_digests


def write_bundle(
    subject, evaluations, policies, decision, readiness, stage, producer_evidence=None
):
    require(stage in {"shadow", "enroll", "queue", "contract-replay"}, "invalid_stage")
    require(decision in {"eligible", "hold", "would_allow"}, "invalid_decision")
    require(readiness in {"eligible", "hold", "not_assessed"}, "invalid_readiness")
    require(evaluations and len(evaluations) <= 3, "missing_evaluation")
    logs, rows, evidence, observations = {}, [], {}, {}
    for name, result in evaluations.items():
        require(name in {"readiness", "candidate", "pilot"}, "invalid_evaluation")
        require(result["engine"] == "gemara", "wrong_engine")
        assessments = result["assessments"]
        require(bool(assessments), "missing_assessments")
        require(
            result["decision"]
            == (
                "eligible"
                if all(r["state"] == "passed" for r in assessments)
                else "hold"
            ),
            "inconsistent_result",
        )
        log = result["evaluation_log"]
        expected = {
            (r["id"], r["policy"], r["plan"], r["requirement"], r["state"])
            for r in assessments
        }
        actual = []
        for control in log["evaluations"]:
            for item in control.get("assessment-logs", []):
                actual.append(
                    (
                        control["control"]["entry-id"],
                        item["plan"]["reference-id"],
                        item["plan"]["entry-id"],
                        item["requirement"]["entry-id"],
                        item["result"].lower(),
                    )
                )
        require(
            len(expected) == len(assessments) == len(actual)
            and expected == set(actual),
            "incomplete_evaluation_log",
        )
        require(
            (log["result"] == "Passed") == (result["decision"] == "eligible"),
            "inconsistent_evaluation_log",
        )
        logs[name + "-evaluation-log.json"] = result["evaluation_log"]
        for row in assessments:
            # Narrative review text and raw API bodies are deliberately not inputs.
            selected = {
                k: row[k]
                for k in ["id", "policy", "plan", "requirement", "state", "reason"]
            }
            require(
                all(
                    isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", v)
                    for v in selected.values()
                ),
                "invalid_assessment",
            )
            rows.append(dict(selected, evaluation=name))
        evidence[name] = {
            "request_sha256": result["request_sha256"],
            "log_sha256": digest(result["evaluation_log"]),
        }
        observations[name] = [
            item
            for control in result["evaluation_log"]["evaluations"]
            for assessment in control.get("assessment-logs", [])
            for item in assessment.get("evidence", [])
        ]
    require(
        set(subject)
        <= {"repository", "pull_request", "head_sha", "base_sha", "evaluated_sha"},
        "invalid_report_subject",
    )
    require(
        subject.get("repository") == "fullsend-ai/auto-merge", "wrong_report_repository"
    )
    for key, value in subject.items():
        if key.endswith("sha"):
            require(
                isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value),
                "invalid_report_subject",
            )
        elif key == "pull_request":
            require(
                type(value) is int and 0 < value < 1000000, "invalid_report_subject"
            )
    report = {
        "schema_version": "gemara-result-bundle/v1",
        "subject": subject,
        "stage": stage,
        "decision": decision,
        "production_readiness": readiness,
        "assessments": rows,
        "evidence_references": evidence,
        "effective_policy_sha256": {k: digest(v) for k, v in policies.items()},
        "bundle_is_authorization": False,
        "source_digests": source_digests(),
    }
    build = load(ROOT / "evaluator-build-lock.json")
    report["native_evaluator"] = {
        k: build[k]
        for k in [
            "sdk_commit",
            "sdk_module",
            "sdk_schema_version",
            "evaluator_binary_sha256",
        ]
    }
    files = dict(
        logs,
        **{
            "decision.json": report,
            "effective-policy.json": policies,
            "normalized-evidence.json": observations,
        },
    )
    if producer_evidence is not None:
        reference = {
            k: producer_evidence[k]
            for k in [
                "reason",
                "payload_sha256",
                "run_id",
                "run_attempt",
                "artifact_id",
                "subject",
            ]
            if k in producer_evidence
        }
        report["producer_evidence"] = reference
        files["review-evidence-reference.json"] = reference
    destination = new_output("bundle")
    for name, value in files.items():
        (destination / name).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )
    text = (
        "# Gemara evaluation evidence\n\n"
        f"Stage: **{stage}**. Decision: **{decision}**. Production readiness: **{readiness}**.\n\n"
        "A completed workflow is not a passing policy. This bundle carries no merge authority.\n\n"
        + "\n".join(
            f"- {r['evaluation']} / {r['id']}: **{r['state']}** ({r['reason']}); policy `{r['policy']}`, plan `{r['plan']}`."
            for r in rows
        )
        + "\n\nDownload this job's `gemara-evaluation` artifact for the native EvaluationLogs, effective policy and digest manifest.\n"
    )
    (destination / "summary.md").write_text(text)
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(destination.iterdir())
    }
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "gemara-bundle-manifest/v1",
                "files": manifest,
                "signed": False,
            },
            indent=2,
        )
        + "\n"
    )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a") as stream:
            stream.write("bundle_path=" + str(destination) + "\n")
    return destination


def write_failure(code, stage):
    """Retain a stable failure code, never exception strings or API responses."""
    if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,80}", code):
        code = "evaluation_failed"
    destination = new_output("bundle")
    (destination / "decision.json").write_text(
        json.dumps(
            {
                "decision": "hold",
                "stage": stage,
                "error": code,
                "bundle_is_authorization": False,
            }
        )
        + "\n"
    )
    (destination / "summary.md").write_text(
        f"# Gemara evaluation held\n\nReason: `{code}`. No passing policy or merge authorization is established.\n"
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a") as stream:
            stream.write(
                f"\n## Evaluation or action held\n\n`{code}`. No successful merge action is established by this step.\n"
            )
    return destination
