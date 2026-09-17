#!/usr/bin/env python3
"""Trusted Auto-Merge postflight and exact-head mutation."""

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

from auto_merge_gate import GateError, ISSUE_URL_RE, canonical_hash, csv_values


DECISIONS = {"APPROVE", "REJECT", "ESCALATE"}
BINDING_KEYS = {
    "repository",
    "pull_request_number",
    "head_sha",
    "base_ref",
    "base_sha",
    "policy_version",
    "evidence_sha256",
}


def gh(*args: str, input_text: str | None = None) -> str:
    if not os.environ.get("GH_TOKEN"):
        raise GateError("GH_TOKEN is not set")
    proc = subprocess.run(
        ["gh", *args],
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=45,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gh error"
        raise GateError(f"GitHub mutation failed: {detail[:500]}")
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
        f"- Policy: `{binding['policy_version']}`\n"
        f"- Evidence: `{binding['evidence_sha256']}`\n"
        f"- Workflow: {run_url or 'local dry run'}\n"
        f"- Recorded: `{dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}`\n\n"
        f"{detail}\n\n{reasons}\n"
    )


def post_receipt(repository: str, number: int, body: str) -> None:
    if os.environ.get("AUTO_MERGE_DRY_RUN") == "1":
        print(body)
        return
    gh(
        "api",
        "--method",
        "POST",
        f"repos/{repository}/issues/{number}/comments",
        "--input",
        "-",
        input_text=json.dumps({"body": body}),
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
    return {key: value for key, value in binding.items() if key != "evidence_sha256"}


def finalize(args: argparse.Namespace) -> int:
    evidence = read_object(Path(args.evidence), "preflight evidence")
    if evidence.get("evidence_sha256") != canonical_hash(evidence):
        raise GateError("preflight evidence hash is invalid")
    if evidence.get("binding", {}).get("evidence_sha256") != evidence.get("evidence_sha256"):
        raise GateError("preflight binding evidence hash is invalid")
    if evidence.get("deterministic", {}).get("eligible") is not True:
        raise GateError("preflight evidence was not eligible")
    policy = trusted_policy(args)
    if evidence.get("policy") != policy:
        raise GateError("preflight policy does not exactly match trusted runner policy")

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

    # A durable write-ahead receipt must succeed before any merge attempt.
    post_receipt(
        repository,
        number,
        receipt_markdown(result, evidence, "decision recorded", "Postflight has not yet authorized a merge."),
    )

    if result["decision"] != "APPROVE":
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "not merged", "The semantic decision did not authorize merge."),
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="auto-merge-postflight-") as tmp:
        fresh = collect_fresh(args, Path(tmp) / "evidence.json")

    if fresh.get("evidence_sha256") != canonical_hash(fresh):
        raise GateError("postflight evidence hash is invalid")
    if fresh.get("deterministic", {}).get("eligible") is not True:
        failures = fresh.get("deterministic", {}).get("failures", [])
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "stale decision rejected", "Postflight failed: " + "; ".join(failures)),
        )
        return 0
    if comparable_binding(fresh["binding"]) != comparable_binding(binding):
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "stale decision rejected", "The head or base binding changed before mutation."),
        )
        return 0

    if os.environ.get("AUTO_MERGE_DRY_RUN") == "1":
        print("auto-merge: dry run; exact-head merge was not attempted")
        return 0

    response_text = gh(
        "api",
        "--method",
        "PUT",
        f"repos/{repository}/pulls/{number}/merge",
        "-f",
        f"sha={binding['head_sha']}",
        "-f",
        "merge_method=squash",
        "-f",
        f"commit_title=Auto-merge PR #{number}",
    )
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise GateError("merge endpoint returned invalid JSON") from exc
    if response.get("merged") is not True:
        raise GateError("exact-head merge was rejected: " + str(response.get("message", "unknown reason"))[:500])

    try:
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "merged", f"Merged exact head `{binding['head_sha']}` by squash."),
        )
    except GateError as exc:
        print(f"auto-merge warning: merge succeeded but outcome receipt failed: {exc}", file=sys.stderr)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--issue-url", required=True)
    result.add_argument("--allowed-repository", required=True)
    result.add_argument("--base-ref", required=True)
    result.add_argument("--policy-version", required=True)
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
