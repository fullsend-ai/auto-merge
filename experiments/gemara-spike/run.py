#!/usr/bin/env python3
"""A credential-free local recommendation demo. No forge or model client."""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import time

from engine import (
    InputError,
    VERSION,
    digest,
    evaluate,
    gemara_log,
    resolve_policy,
    validate_input,
)
from validate import ValidationError, validate

ROOT = Path(__file__).resolve().parent


def _unique(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise InputError("duplicate_json_key")
        value[key] = item
    return value


def load(path: Path) -> dict:
    if path.is_symlink():
        raise InputError("symlink_input")
    if not path.is_file():
        raise InputError("regular_file_input_required")
    limit = 1024 * 1024
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise InputError("input_too_large")
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                InputError("invalid_json_constant")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError("invalid_json") from exc
    if not isinstance(data, dict):
        raise InputError("invalid_document")
    return data


def timestamp() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def execute(evidence: dict, profile: str) -> dict:
    if profile not in {"baseline", "repository"}:
        raise InputError("unsupported_profile")
    validate_input(evidence)
    catalog = load(ROOT / "catalog.json")
    policy = load(ROOT / "policies" / (profile + ".json"))
    begin = time.perf_counter()
    validate(catalog, "ControlCatalog")
    validate(policy, "Policy")
    input_validation_ms = (time.perf_counter() - begin) * 1000
    effective = resolve_policy(catalog, policy)
    started = timestamp()
    begin = time.perf_counter()
    report = evaluate(evidence, effective)
    evaluation_ms = (time.perf_counter() - begin) * 1000
    ended = timestamp()
    # Plain JSON and Gemara use the same evaluator: this isolates representation costs.
    plain = {
        "decision": report["decision"],
        "mutation_permitted": False,
        "states": {r["control_id"]: r["state"] for r in report["assessments"]},
    }
    log = gemara_log(catalog, policy, evidence, report, started, ended)
    begin = time.perf_counter()
    validate(log, "EvaluationLog")
    log_validation_ms = (time.perf_counter() - begin) * 1000
    comparison = {
        "method": "same custom evaluator; compare plain JSON representation with validated Gemara representation",
        "decisions_match": (log["result"] == "Passed")
        == (plain["decision"] == "eligible_for_demo_only"),
        "plain_json_bytes": len(json.dumps(plain, sort_keys=True).encode()),
        "gemara_log_bytes": len(json.dumps(log, sort_keys=True).encode()),
        "evaluation_ms": round(evaluation_ms, 3),
        "input_schema_validation_ms": round(input_validation_ms, 3),
        "evaluation_log_validation_ms": round(log_validation_ms, 3),
        "llm_calls": 0,
    }
    return {
        "input.json": evidence,
        "catalog.json": catalog,
        "policy.json": policy,
        "effective-policy.json": effective,
        "recommendation.json": report,
        "evaluation.json": log,
        "plain-baseline.json": plain,
        "comparison.json": comparison,
        "run.json": {
            "evaluator_version": VERSION,
            "started_at": started,
            "ended_at": ended,
            "evaluation_as_of": evidence["evaluation_time"],
            "provenance": "synthetic",
            "profile": profile,
            "evaluator_sources": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ["engine.py", "run.py", "adapters.py", "validate.py"]
            },
            "tool_lock_sha256": digest(load(ROOT / "tool-lock.json")),
            "official_schema_validation": "passed",
            "network_used_by_evaluator": False,
            "llm_used": False,
            "mutation_permitted": False,
        },
    }


def write_output(package: dict, destination: Path) -> None:
    allowed = ROOT / "out"
    if allowed.is_symlink() or not destination.resolve().is_relative_to(
        allowed.resolve()
    ):
        raise InputError("output_must_be_in_local_out")
    if destination.exists() or any(
        p.is_symlink()
        for p in [destination, *destination.parents]
        if p.is_relative_to(ROOT)
    ):
        raise InputError("output_exists_or_is_symlink")
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in package.items():
        with (destination / name).open("x") as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
    report = package["recommendation.json"]
    rows = "\n".join(
        f"- {r['control_id']}: **{r['state']}**; evidence: {', '.join(r['evidence_ids']) or 'none'}; reasons: {', '.join(r['reasons']) or 'none'}."
        for r in report["assessments"]
    )
    (destination / "report.md").write_text(
        f"# Synthetic demo: {report['scenario']}\n\nDecision: **{report['decision']}**. No mutation is permitted.\n\n{rows}\n\nTrace: input → effective policy → control/requirement → evidence IDs and digests → Gemara evaluation → recommendation.\n"
    )
    hashes = {
        p.name: digest(json.loads(p.read_text())) for p in destination.glob("*.json")
    }
    (destination / "artifact-hashes.json").write_text(
        json.dumps(hashes, indent=2) + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--policy", choices=["baseline", "repository"], default="baseline"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new directory inside this experiment's ignored out/",
    )
    args = parser.parse_args()
    try:
        package = execute(load(args.evidence), args.policy)
        write_output(package, args.output)
        report = package["recommendation.json"]
        print(
            json.dumps(
                {
                    "scenario": report["scenario"],
                    "decision": report["decision"],
                    "mutation_permitted": False,
                    "states": {
                        r["control_id"]: r["state"] for r in report["assessments"]
                    },
                },
                sort_keys=True,
            )
        )
        return 0
    except (InputError, ValidationError) as exc:
        print(
            json.dumps(
                {"error": str(exc), "decision": "hold", "mutation_permitted": False}
            )
        )
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(
            json.dumps(
                {
                    "error": "invalid_input_or_output",
                    "decision": "hold",
                    "mutation_permitted": False,
                }
            )
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
