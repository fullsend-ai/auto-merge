#!/usr/bin/env python3
"""Validate semantic authorization and ask the SCM to use its configured merge path."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from auto_merge_gate import ISSUE_URL_RE, canonical_hash, policy_fingerprint


DECISIONS = {"AUTHORIZE", "DEFER", "ESCALATE"}
MODES = {"observe", "lab-automatic"}
SCM_OPERATION = "native-auto-merge"
TRUSTED_RECEIPT_AUTHORS = {"fullsend-ai-coder[bot]"}
BINDING_KEYS = {
    "repository",
    "pull_request_number",
    "head_sha",
    "base_ref",
    "base_sha",
    "policy_fingerprint",
    "semantic_fingerprint",
    "context_fingerprint",
}
RECEIPT_RE = re.compile(
    r"^<!-- fullsend:auto-merge-receipt:(?P<key>[0-9a-f]{64}):(?P<phase>[a-z-]+) -->\n"
    r"### Auto-Merge: (?P=phase)\n\n"
    r"- Decision: `(?P<decision>AUTHORIZE|DEFER|ESCALATE)`\n"
    r"- Head: `(?P<head>[0-9a-f]{40})`\n"
    r"- Base: `(?P<base_ref>[^`@\n]+)@(?P<base_sha>[0-9a-f]{40})`\n"
    r"- Policy: `(?P<policy>[0-9a-f]{64})`\n"
    r"- Semantic context: `(?P<semantic>[0-9a-f]{64})`\n"
    r"- Context: `(?P<context>[0-9a-f]{64})`\n"
    r"- Idempotency key: `(?P<marker_key>[0-9a-f]{64})`\n",
    re.MULTILINE,
)


class GateError(RuntimeError):
    """Trusted postflight rejected the model result or current context."""


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def gh(*args: str) -> str:
    proc = subprocess.run(
        ["gh", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gh error"
        raise GateError(f"GitHub command failed: {detail[:500]}")
    return proc.stdout


def read_object(path: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"{name} is missing or invalid JSON") from exc
    if not isinstance(value, dict):
        raise GateError(f"{name} must be a JSON object")
    return value


def validate_result(result: dict[str, Any], evidence: dict[str, Any]) -> None:
    decision = result.get("decision")
    if decision not in DECISIONS:
        raise GateError("model decision is invalid")
    binding = result.get("binding")
    if not isinstance(binding, dict) or set(binding) != BINDING_KEYS:
        raise GateError("model binding has missing or extra fields")
    if binding != evidence.get("binding"):
        raise GateError("model binding does not exactly match semantic evidence")
    reasons = result.get("reasons")
    blockers = result.get("blocking_signals")
    summary = result.get("summary")
    comment_ids = result.get("evidence_comment_ids")
    if not isinstance(summary, str) or not summary or "\n" in summary or len(summary) > 240:
        raise GateError("model summary is invalid")
    if not isinstance(reasons, list) or not 1 <= len(reasons) <= 8 or not all(isinstance(x, str) and x for x in reasons):
        raise GateError("model reasons are invalid")
    if not isinstance(blockers, list) or len(blockers) > 10 or not all(isinstance(x, str) and x for x in blockers):
        raise GateError("model blocking_signals are invalid")
    if not isinstance(comment_ids, list) or len(comment_ids) > 100 or not all(isinstance(x, int) and x > 0 for x in comment_ids):
        raise GateError("model evidence_comment_ids are invalid")
    if decision == "AUTHORIZE" and blockers:
        raise GateError("AUTHORIZE cannot contain blocking signals")
    if evidence.get("prerequisites", {}).get("ready_for_semantic_evaluation") is not True:
        raise GateError("trusted semantic prerequisites are not satisfied")


def trusted_policy(args: argparse.Namespace) -> dict[str, Any]:
    policy = {
        "repository": args.allowed_repository,
        "base_ref": args.base_ref,
        "policy_version": args.policy_version,
        "mode": args.mode,
        "semantic_reviewer": args.semantic_reviewer,
        "risk_assessment_producer": args.risk_assessment_producer,
        "artifact_correlation_minutes": args.artifact_correlation_minutes,
        "maximum_unattended_risk": args.maximum_unattended_risk,
        "human_signal_associations": sorted(csv_values(args.human_signal_associations)),
        "review_quality_mode": args.review_quality_mode,
        "review_quality_minimum_score": args.review_quality_minimum_score,
        "review_quality_minimum_samples": args.review_quality_minimum_samples,
        "custom_instructions": args.custom_instructions,
    }
    if policy["mode"] not in MODES:
        raise GateError("trusted mode is unsupported")
    if not policy["semantic_reviewer"] or not policy["risk_assessment_producer"] or not policy["human_signal_associations"]:
        raise GateError("trusted semantic policy is incomplete")
    return policy


def collect_fresh(args: argparse.Namespace, destination: Path) -> dict[str, Any]:
    policy = trusted_policy(args)
    command = [
        sys.executable,
        args.gate_script,
        "collect",
        "--issue-url",
        args.issue_url,
        "--repository",
        policy["repository"],
        "--base-ref",
        policy["base_ref"],
        "--policy-version",
        policy["policy_version"],
        "--mode",
        policy["mode"],
        "--semantic-reviewer",
        policy["semantic_reviewer"],
        "--risk-assessment-producer",
        policy["risk_assessment_producer"],
        "--artifact-correlation-minutes",
        str(policy["artifact_correlation_minutes"]),
        "--maximum-unattended-risk",
        policy["maximum_unattended_risk"],
        "--human-signal-associations",
        ",".join(policy["human_signal_associations"]),
        "--review-quality-mode",
        policy["review_quality_mode"],
        "--review-quality-minimum-score",
        str(policy["review_quality_minimum_score"]),
        "--review-quality-minimum-samples",
        str(policy["review_quality_minimum_samples"]),
        "--custom-instructions",
        policy["custom_instructions"],
        "--output",
        str(destination),
    ]
    if args.review_quality_file:
        command.extend(["--review-quality-file", args.review_quality_file])
    proc = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90, env=os.environ.copy())
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown collector error"
        raise GateError(f"fresh semantic evidence collection failed: {detail[:500]}")
    return read_object(destination, "fresh semantic evidence")


def comparable_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in binding.items() if key != "context_fingerprint"}


def idempotency_key(binding: dict[str, Any], strategy: str) -> str:
    payload = {
        "repository": binding["repository"],
        "pull_request_number": binding["pull_request_number"],
        "head_sha": binding["head_sha"],
        "base_ref": binding["base_ref"],
        "base_sha": binding["base_sha"],
        "policy_fingerprint": binding["policy_fingerprint"],
        "semantic_fingerprint": binding["semantic_fingerprint"],
        "strategy": strategy,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def receipt_markdown(
    result: dict[str, Any],
    evidence: dict[str, Any],
    phase: str,
    detail: str,
    request_key: str | None = None,
) -> str:
    binding = result["binding"]
    key = request_key or idempotency_key(binding, SCM_OPERATION)
    workflow = os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" + os.environ.get("GITHUB_REPOSITORY", binding["repository"])
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    reasons = "\n".join(f"- {reason}" for reason in result["reasons"])
    blockers = "\n".join(f"- Blocking: {signal}" for signal in result["blocking_signals"])
    return (
        f"<!-- fullsend:auto-merge-receipt:{key}:{phase} -->\n"
        f"### Auto-Merge: {phase}\n\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Head: `{binding['head_sha']}`\n"
        f"- Base: `{binding['base_ref']}@{binding['base_sha']}`\n"
        f"- Policy: `{binding['policy_fingerprint']}`\n"
        f"- Semantic context: `{binding['semantic_fingerprint']}`\n"
        f"- Context: `{binding['context_fingerprint']}`\n"
        f"- Idempotency key: `{key}`\n"
        f"- Workflow: {workflow}/actions/runs/{run_id}\n"
        f"- Recorded: `{dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}`\n\n"
        f"{detail}\n\n{reasons}\n{blockers}\n"
    )


def parse_receipt_header(body: str) -> dict[str, str] | None:
    match = RECEIPT_RE.match(body)
    return match.groupdict() if match else None


def post_receipt(repository: str, number: int, body: str) -> None:
    gh("pr", "comment", str(number), "--repo", repository, "--body", body)


def existing_receipt_phases(repository: str, number: int, request_key: str) -> set[str]:
    payload = json.loads(gh("api", f"repos/{repository}/issues/{number}/comments?per_page=100"))
    phases: set[str] = set()
    for comment in payload if isinstance(payload, list) else []:
        if str((comment.get("user") or {}).get("login") or "") not in TRUSTED_RECEIPT_AUTHORS:
            continue
        parsed = parse_receipt_header(str(comment.get("body") or ""))
        if parsed and parsed["key"] == request_key and parsed["marker_key"] == request_key:
            phases.add(parsed["phase"])
    return phases


def finalize(args: argparse.Namespace) -> int:
    evidence = read_object(Path(args.evidence), "semantic evidence")
    if evidence.get("context_fingerprint") != canonical_hash(evidence):
        raise GateError("semantic evidence context fingerprint is invalid")
    policy = trusted_policy(args)
    if evidence.get("policy") != policy or evidence.get("binding", {}).get("policy_fingerprint") != policy_fingerprint(policy):
        raise GateError("semantic evidence policy does not match trusted runner policy")
    result = read_object(Path(args.result), "model result")
    validate_result(result, evidence)
    binding = evidence["binding"]
    repository = binding["repository"]
    number = int(binding["pull_request_number"])
    issue_match = ISSUE_URL_RE.fullmatch(args.issue_url)
    if issue_match is None or issue_match.group("repo") != repository or int(issue_match.group("number")) != number:
        raise GateError("semantic binding does not match the trusted pull request URL")

    if result["decision"] != "AUTHORIZE":
        phase = "deferred" if result["decision"] == "DEFER" else "escalated"
        body = receipt_markdown(result, evidence, phase, "No SCM merge request was made; semantic context requires human attention.")
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0

    with tempfile.TemporaryDirectory(prefix="auto-merge-postflight-") as tmp:
        fresh = collect_fresh(args, Path(tmp) / "evidence.json")
    if fresh.get("context_fingerprint") != canonical_hash(fresh):
        raise GateError("fresh semantic context fingerprint is invalid")
    if fresh.get("prerequisites", {}).get("ready_for_semantic_evaluation") is not True:
        failures = fresh.get("prerequisites", {}).get("failures", [])
        body = receipt_markdown(result, evidence, "stale", "Fresh semantic prerequisites failed: " + "; ".join(failures))
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0
    if comparable_binding(fresh["binding"]) != comparable_binding(binding):
        body = receipt_markdown(result, evidence, "stale", "The exact revision, base, policy, or semantic context changed before SCM submission.")
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0

    if policy["mode"] == "observe":
        print(receipt_markdown(result, evidence, "observed", "Semantic authorization passed. Observe mode made no SCM request."))
        return 0

    request_key = idempotency_key(binding, SCM_OPERATION)
    phases = existing_receipt_phases(repository, number, request_key)
    if phases & {"pending", "submitted"}:
        print(f"auto-merge: request {request_key} already has phases {sorted(phases)}; no duplicate SCM request issued")
        return 0

    post_receipt(repository, number, receipt_markdown(result, evidence, "pending", "Semantic authorization passed; SCM submission is pending.", request_key))

    with tempfile.TemporaryDirectory(prefix="auto-merge-final-context-") as tmp:
        final = collect_fresh(args, Path(tmp) / "evidence.json")
    if final.get("context_fingerprint") != canonical_hash(final) or comparable_binding(final["binding"]) != comparable_binding(binding):
        post_receipt(repository, number, receipt_markdown(result, evidence, "aborted", "Semantic context changed after the pending receipt; no SCM request was made.", request_key))
        return 0

    try:
        gh(
            "pr",
            "merge",
            str(number),
            "--repo",
            repository,
            "--auto",
            "--squash",
            "--match-head-commit",
            binding["head_sha"],
        )
    except GateError as exc:
        post_receipt(repository, number, receipt_markdown(result, evidence, "scm-rejected", "GitHub rejected the request; no policy was bypassed.", request_key))
        raise GateError("SCM submission failed closed") from exc

    post_receipt(
        repository,
        number,
        receipt_markdown(
            result,
            evidence,
            "submitted",
            "Semantic authorization was submitted. GitHub now exclusively controls checks, reviews, branch policy, queueing, and final merge.",
            request_key,
        ),
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--issue-url", required=True)
    result.add_argument("--allowed-repository", required=True)
    result.add_argument("--base-ref", required=True)
    result.add_argument("--policy-version", required=True)
    result.add_argument("--mode", required=True, choices=sorted(MODES))
    result.add_argument("--semantic-reviewer", required=True)
    result.add_argument("--risk-assessment-producer", required=True)
    result.add_argument("--artifact-correlation-minutes", required=True, type=int)
    result.add_argument("--maximum-unattended-risk", required=True)
    result.add_argument("--human-signal-associations", required=True)
    result.add_argument("--review-quality-mode", required=True)
    result.add_argument("--review-quality-minimum-score", required=True, type=float)
    result.add_argument("--review-quality-minimum-samples", required=True, type=int)
    result.add_argument("--review-quality-file", default="")
    result.add_argument("--custom-instructions", required=True)
    result.add_argument("--evidence", required=True)
    result.add_argument("--result", required=True)
    result.add_argument("--gate-script", required=True)
    return result


def main() -> int:
    try:
        return finalize(parser().parse_args())
    except (GateError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"auto-merge postflight failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
