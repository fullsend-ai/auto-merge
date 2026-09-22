#!/usr/bin/env python3
"""Trusted Auto-Merge postflight for the observe-only POC."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from auto_merge_gate import GateError, ISSUE_URL_RE, canonical_hash, csv_values, policy_fingerprint


DECISIONS = {"APPROVE", "REJECT", "ESCALATE"}
BINDING_KEYS = {
    "repository",
    "pull_request_number",
    "head_sha",
    "base_ref",
    "base_sha",
    "policy_fingerprint",
    "context_fingerprint",
}


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
        raise GateError("model binding does not exactly match preflight evidence")
    reasons = result.get("reasons")
    risks = result.get("risk_signals")
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary or "\n" in summary or len(summary) > 200:
        raise GateError("model summary is invalid")
    if not isinstance(reasons, list) or not 1 <= len(reasons) <= 5 or not all(isinstance(x, str) and x for x in reasons):
        raise GateError("model reasons are invalid")
    if not isinstance(risks, list) or len(risks) > 10 or not all(isinstance(x, str) and x for x in risks):
        raise GateError("model risk_signals are invalid")
    if decision == "APPROVE" and risks:
        raise GateError("APPROVE cannot contain risk signals")


def trusted_policy(args: argparse.Namespace) -> dict[str, Any]:
    """Build policy only from trusted runner arguments, never model-visible evidence."""
    policy = {
        "repository": args.allowed_repository,
        "base_ref": args.base_ref,
        "policy_version": args.policy_version,
        "mode": args.mode,
        "required_checks": csv_values(args.required_checks),
        "allowed_paths": csv_values(args.allowed_paths),
        "allowed_authors": csv_values(args.allowed_authors),
    }
    if not policy["required_checks"] or not policy["allowed_paths"] or not policy["allowed_authors"]:
        raise GateError("trusted policy inputs must be non-empty")
    return policy


def receipt_markdown(
    result: dict[str, Any],
    evidence: dict[str, Any],
    phase: str,
    detail: str,
) -> str:
    binding = evidence["binding"]
    reasons = "\n".join(f"- {reason}" for reason in result["reasons"])
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY"):
        run_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return (
        "<!-- fullsend:auto-merge-receipt -->\n"
        f"### Auto-Merge: {phase}\n\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Head: `{binding['head_sha']}`\n"
        f"- Base: `{binding['base_ref']}@{binding['base_sha']}`\n"
        f"- Policy: `{binding['policy_fingerprint']}`\n"
        f"- Context: `{binding['context_fingerprint']}`\n"
        f"- Workflow: {run_url or 'local dry run'}\n"
        f"- Recorded: `{dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}`\n\n"
        f"{detail}\n\n{reasons}\n"
    )


def collect_fresh(args: argparse.Namespace, destination: Path) -> dict[str, Any]:
    policy = trusted_policy(args)
    command = [
        "python3",
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
        "--required-checks",
        ",".join(policy["required_checks"]),
        "--allowed-paths",
        ",".join(policy["allowed_paths"]),
        "--allowed-authors",
        ",".join(policy["allowed_authors"]),
        "--output",
        str(destination),
    ]
    proc = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if proc.returncode != 0:
        raise GateError("postflight evidence collection failed: " + proc.stderr.strip()[-500:])
    return read_object(destination, "postflight evidence")


def comparable_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in binding.items() if key != "context_fingerprint"}


def finalize(args: argparse.Namespace) -> int:
    evidence = read_object(Path(args.evidence), "preflight evidence")
    if evidence.get("context_fingerprint") != canonical_hash(evidence):
        raise GateError("preflight context fingerprint is invalid")
    if evidence.get("binding", {}).get("context_fingerprint") != evidence.get("context_fingerprint"):
        raise GateError("preflight binding context fingerprint is invalid")
    if evidence.get("deterministic", {}).get("eligible") is not True:
        raise GateError("preflight evidence was not eligible")
    policy = trusted_policy(args)
    if evidence.get("policy") != policy:
        raise GateError("preflight policy does not exactly match trusted runner policy")
    if evidence.get("binding", {}).get("policy_fingerprint") != policy_fingerprint(policy):
        raise GateError("preflight policy fingerprint does not match trusted runner policy")
    if policy["mode"] != "observe":
        raise GateError("this POC is intentionally limited to observe mode")

    result = read_object(Path(args.result), "model result")
    validate_result(result, evidence)
    binding = evidence["binding"]
    repository = binding["repository"]
    number = int(binding["pull_request_number"])
    issue_match = ISSUE_URL_RE.fullmatch(args.issue_url)
    if (
        issue_match is None
        or issue_match.group("repo") != args.allowed_repository
        or int(issue_match.group("number")) != number
        or repository != args.allowed_repository
    ):
        raise GateError("preflight binding does not match the trusted repository and pull request URL")

    # Observe mode records to the run log and performs no GitHub mutation.
    print(receipt_markdown(result, evidence, "decision observed", "Postflight has not yet authorized a merge."))

    if result["decision"] != "APPROVE":
        print(receipt_markdown(result, evidence, "not merged", "The semantic decision did not authorize merge."))
        return 0

    with tempfile.TemporaryDirectory(prefix="auto-merge-postflight-") as tmp:
        fresh = collect_fresh(args, Path(tmp) / "evidence.json")

    if fresh.get("context_fingerprint") != canonical_hash(fresh):
        raise GateError("postflight context fingerprint is invalid")
    if fresh.get("deterministic", {}).get("eligible") is not True:
        failures = fresh.get("deterministic", {}).get("failures", [])
        print(receipt_markdown(result, evidence, "stale decision rejected", "Postflight failed: " + "; ".join(failures)))
        return 0
    if comparable_binding(fresh["binding"]) != comparable_binding(binding):
        print(receipt_markdown(result, evidence, "stale decision rejected", "The head, base, policy, or context binding changed before mutation."))
        return 0

    print(receipt_markdown(result, evidence, "observe preview", "All final gates passed. Observe mode did not attempt a merge."))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--issue-url", required=True)
    result.add_argument("--allowed-repository", required=True)
    result.add_argument("--base-ref", required=True)
    result.add_argument("--policy-version", required=True)
    result.add_argument("--mode", required=True, choices=["observe"])
    result.add_argument("--required-checks", required=True)
    result.add_argument("--allowed-paths", required=True)
    result.add_argument("--allowed-authors", required=True)
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
