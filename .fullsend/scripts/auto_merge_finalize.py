#!/usr/bin/env python3
"""Trusted Auto-Merge postflight and lab-scoped exact-head mutation."""

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

from auto_merge_gate import GateError, ISSUE_URL_RE, canonical_hash, csv_values, policy_fingerprint


DECISIONS = {"APPROVE", "REJECT", "ESCALATE"}
MODES = {"observe", "lab-automatic"}
EXECUTION_STRATEGIES = {"direct", "queue"}
RISK_LEVELS = {"low", "moderate", "elevated", "high", "critical"}
TRUSTED_RECEIPT_AUTHORS = {"fullsend-ai-coder[bot]"}
RECEIPT_PHASES = {
    "aborted",
    "merged",
    "not-merged",
    "not-queued",
    "observe-preview",
    "outcome-unknown",
    "pending",
    "queued",
    "reconciled-merged",
    "stale-decision-rejected",
}
RECEIPT_HEADER_RE = re.compile(
    r"\A<!-- fullsend:auto-merge-receipt:(?P<marker_key>[0-9a-f]{64}|observation):"
    r"(?P<phase>[a-z][a-z-]*) -->\n"
    r"### Auto-Merge: (?P<title>[^\n]+)\n\n"
    r"- Decision: `(?P<decision>APPROVE|REJECT|ESCALATE)`\n"
    r"- Head: `(?P<head>[0-9a-f]{40})`\n"
    r"- Base: `(?P<base_ref>[A-Za-z0-9._/-]+)@(?P<base_sha>[0-9a-f]{40})`\n"
    r"- Policy: `(?P<policy>[0-9a-f]{64})`\n"
    r"- Context: `(?P<context>[0-9a-f]{64})`\n"
    r"- Idempotency key: `(?P<idempotency>[0-9a-f]{64}|not-applicable)`\n"
)
BINDING_KEYS = {
    "repository",
    "pull_request_number",
    "head_sha",
    "base_ref",
    "base_sha",
    "policy_fingerprint",
    "context_fingerprint",
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
        raise GateError(f"GitHub request failed: {detail[:500]}")
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
        "mode": args.mode,
        "execution_strategy": args.execution_strategy,
        "risk_gate": args.risk_gate,
        "allowed_risk_levels": csv_values(args.allowed_risk_levels),
        "required_checks": csv_values(args.required_checks),
        "allowed_paths": csv_values(args.allowed_paths),
        "allowed_authors": csv_values(args.allowed_authors),
        "allowed_reviewers": csv_values(args.allowed_reviewers),
    }
    if (
        not policy["required_checks"]
        or not policy["allowed_paths"]
        or not policy["allowed_authors"]
        or not policy["allowed_reviewers"]
    ):
        raise GateError("trusted policy inputs must be non-empty")
    if policy["mode"] not in MODES:
        raise GateError("trusted policy mode is unsupported")
    if policy["execution_strategy"] not in EXECUTION_STRATEGIES:
        raise GateError("trusted execution strategy is unsupported")
    if policy["risk_gate"] not in {"informational", "required"}:
        raise GateError("trusted risk gate is unsupported")
    if policy["risk_gate"] == "required" and not policy["allowed_risk_levels"]:
        raise GateError("trusted risk gate requires allowed levels")
    if any(level not in RISK_LEVELS for level in policy["allowed_risk_levels"]):
        raise GateError("trusted allowed risk levels contain an unsupported value")
    return policy


def idempotency_key(binding: dict[str, Any], execution_strategy: str) -> str:
    request = {
        "binding": {key: value for key, value in binding.items() if key != "context_fingerprint"},
        "operation": f"{execution_strategy}-merge",
    }
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def receipt_markdown(
    result: dict[str, Any],
    evidence: dict[str, Any],
    phase: str,
    detail: str,
    request_key: str = "",
) -> str:
    binding = evidence["binding"]
    reasons = "\n".join(f"- {reason}" for reason in result["reasons"])
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY"):
        run_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return (
        f"<!-- fullsend:auto-merge-receipt:{request_key or 'observation'}:{phase.lower().replace(' ', '-')} -->\n"
        f"### Auto-Merge: {phase}\n\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Head: `{binding['head_sha']}`\n"
        f"- Base: `{binding['base_ref']}@{binding['base_sha']}`\n"
        f"- Policy: `{binding['policy_fingerprint']}`\n"
        f"- Context: `{binding['context_fingerprint']}`\n"
        f"- Idempotency key: `{request_key or 'not-applicable'}`\n"
        f"- Workflow: {run_url or 'local dry run'}\n"
        f"- Recorded: `{dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}`\n\n"
        f"{detail}\n\n{reasons}\n"
    )


def post_receipt(repository: str, number: int, body: str) -> None:
    gh(
        "api",
        "--method",
        "POST",
        f"repos/{repository}/issues/{number}/comments",
        "--input",
        "-",
        input_text=json.dumps({"body": body}),
    )


def parse_receipt_header(body: str) -> dict[str, str] | None:
    """Parse only canonical receipts emitted at the start of a trusted comment."""
    match = RECEIPT_HEADER_RE.match(body)
    if match is None:
        return None
    receipt = match.groupdict()
    if receipt["phase"] not in RECEIPT_PHASES:
        return None
    if receipt["title"].lower().replace(" ", "-") != receipt["phase"]:
        return None
    if receipt["marker_key"] == "observation":
        if receipt["idempotency"] != "not-applicable":
            return None
    elif receipt["marker_key"] != receipt["idempotency"]:
        return None
    return receipt


def existing_receipt_phases(repository: str, number: int, request_key: str) -> set[str]:
    raw = gh(
        "api",
        "--paginate",
        "--slurp",
        f"repos/{repository}/issues/{number}/comments?per_page=100",
    )
    try:
        pages = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GateError("GitHub comments query returned invalid JSON") from exc
    phases: set[str] = set()
    for page in pages:
        for comment in page if isinstance(page, list) else []:
            author = str((comment.get("user") or {}).get("login") or "")
            if author not in TRUSTED_RECEIPT_AUTHORS:
                continue
            receipt = parse_receipt_header(str(comment.get("body") or ""))
            if receipt is not None and receipt["marker_key"] == request_key:
                phases.add(receipt["phase"])
    return phases


def pull_request_state(repository: str, number: int) -> dict[str, Any]:
    try:
        value = json.loads(gh("api", f"repos/{repository}/pulls/{number}"))
    except json.JSONDecodeError as exc:
        raise GateError("GitHub pull-request query returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise GateError("GitHub pull-request query returned an invalid object")
    return value


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
        "--execution-strategy",
        policy["execution_strategy"],
        "--risk-gate",
        policy["risk_gate"],
        "--allowed-risk-levels",
        ",".join(policy["allowed_risk_levels"]),
        "--required-checks",
        ",".join(policy["required_checks"]),
        "--allowed-paths",
        ",".join(policy["allowed_paths"]),
        "--allowed-authors",
        ",".join(policy["allowed_authors"]),
        "--allowed-reviewers",
        ",".join(policy["allowed_reviewers"]),
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

    if result["decision"] != "APPROVE":
        body = receipt_markdown(result, evidence, "not merged", "The semantic decision did not authorize merge.")
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0

    with tempfile.TemporaryDirectory(prefix="auto-merge-postflight-") as tmp:
        fresh = collect_fresh(args, Path(tmp) / "evidence.json")

    if fresh.get("context_fingerprint") != canonical_hash(fresh):
        raise GateError("postflight context fingerprint is invalid")
    if fresh.get("deterministic", {}).get("eligible") is not True:
        failures = fresh.get("deterministic", {}).get("failures", [])
        body = receipt_markdown(result, evidence, "stale decision rejected", "Postflight failed: " + "; ".join(failures))
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0
    if comparable_binding(fresh["binding"]) != comparable_binding(binding):
        body = receipt_markdown(result, evidence, "stale decision rejected", "The head, base, or policy binding changed before mutation.")
        if policy["mode"] == "observe":
            print(body)
        else:
            post_receipt(repository, number, body)
        return 0

    if policy["mode"] == "observe":
        print(receipt_markdown(result, evidence, "observe preview", "All final gates passed. Observe mode did not attempt a merge."))
        return 0

    request_key = idempotency_key(binding, policy["execution_strategy"])
    phases = existing_receipt_phases(repository, number, request_key)
    if phases:
        pr_state = pull_request_state(repository, number)
        if pr_state.get("merged") is True:
            if "merged" not in phases and "reconciled-merged" not in phases:
                post_receipt(
                    repository,
                    number,
                    receipt_markdown(result, evidence, "reconciled merged", "A prior request already merged this pull request; no second request was issued.", request_key),
                )
            return 0
        print(f"auto-merge: request {request_key} already has receipt phases {sorted(phases)}; no duplicate request issued")
        return 0

    post_receipt(
        repository,
        number,
        receipt_markdown(
            result,
            evidence,
            "pending",
            "Final authorization passed; a queue enrollment is pending."
            if policy["execution_strategy"] == "queue"
            else "Final authorization passed; an exact-head squash merge request is pending.",
            request_key,
        ),
    )

    # Re-run every mutable gate after the durable pending receipt and before the
    # forge request. The lab has no cross-run lease, so any mismatch stops here.
    with tempfile.TemporaryDirectory(prefix="auto-merge-final-authorization-") as tmp:
        final = collect_fresh(args, Path(tmp) / "evidence.json")
    if final.get("context_fingerprint") != canonical_hash(final):
        raise GateError("final authorization context fingerprint is invalid")
    if final.get("deterministic", {}).get("eligible") is not True or comparable_binding(final["binding"]) != comparable_binding(binding):
        failures = final.get("deterministic", {}).get("failures", [])
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "aborted", "Final authorization changed after the pending receipt: " + "; ".join(failures), request_key),
        )
        return 0

    if policy["execution_strategy"] == "queue":
        try:
            gh(
                "pr",
                "merge",
                str(number),
                "--repo",
                repository,
                "--match-head-commit",
                binding["head_sha"],
            )
        except GateError as exc:
            post_receipt(
                repository,
                number,
                receipt_markdown(result, evidence, "not queued", "GitHub rejected merge-queue enrollment.", request_key),
            )
            raise GateError("merge-queue enrollment failed closed") from exc
        post_receipt(
            repository,
            number,
            receipt_markdown(
                result,
                evidence,
                "queued",
                "GitHub accepted the exact approved head for merge-queue processing. The queue-generated revision still requires fresh authorization.",
                request_key,
            ),
        )
        return 0

    try:
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
        response = json.loads(response_text)
    except (GateError, json.JSONDecodeError) as exc:
        pr_state = pull_request_state(repository, number)
        if pr_state.get("merged") is True:
            post_receipt(
                repository,
                number,
                receipt_markdown(result, evidence, "reconciled merged", "The forge response was uncertain, but fresh state proves the pull request merged.", request_key),
            )
            return 0
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "outcome unknown", "The forge request outcome could not be proven; no retry was issued. Operator reconciliation is required.", request_key),
        )
        raise GateError("merge outcome is unknown; operator reconciliation required") from exc

    if response.get("merged") is not True:
        post_receipt(
            repository,
            number,
            receipt_markdown(result, evidence, "not merged", "GitHub rejected the exact-head request: " + str(response.get("message", "unknown reason"))[:500], request_key),
        )
        return 0

    post_receipt(
        repository,
        number,
        receipt_markdown(result, evidence, "merged", f"GitHub accepted the exact-head squash merge for `{binding['head_sha']}`.", request_key),
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--issue-url", required=True)
    result.add_argument("--allowed-repository", required=True)
    result.add_argument("--base-ref", required=True)
    result.add_argument("--policy-version", required=True)
    result.add_argument("--mode", required=True, choices=sorted(MODES))
    result.add_argument("--execution-strategy", required=True, choices=sorted(EXECUTION_STRATEGIES))
    result.add_argument("--risk-gate", required=True, choices=["informational", "required"])
    result.add_argument("--allowed-risk-levels", required=True)
    result.add_argument("--required-checks", required=True)
    result.add_argument("--allowed-paths", required=True)
    result.add_argument("--allowed-authors", required=True)
    result.add_argument("--allowed-reviewers", required=True)
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
