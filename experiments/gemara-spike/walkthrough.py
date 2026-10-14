#!/usr/bin/env python3
"""A controlled, credential-free walkthrough suitable for a public recording."""

import copy

from engine import InputError, resolve_policy
from run import ROOT, execute, load
from validate import validate


def main() -> None:
    catalog = load(ROOT / "catalog.json")
    baseline = load(ROOT / "policies/baseline.json")
    print("ATTEMPT 2 — LOCAL SYNTHETIC GEMARA WALKTHROUGH", flush=True)
    print(
        "All inputs are fabricated. No model, forge action, token or workflow is used.",
        flush=True,
    )
    print("1. Catalog: " + ", ".join(c["id"] for c in catalog["controls"]), flush=True)
    print(
        "2. Baseline selects CI + independent Review; repository profile also requires a scan.",
        flush=True,
    )
    for name, profile in [
        ("satisfied", "baseline"),
        ("failed-ci", "baseline"),
        ("missing-review", "baseline"),
        ("stale-review", "baseline"),
        ("repository-failed", "baseline"),
        ("repository-failed", "repository"),
        ("repository-satisfied", "repository"),
    ]:
        package = execute(load(ROOT / "fixtures" / (name + ".json")), profile)
        report = package["recommendation.json"]
        print("\nCASE " + name + " / " + profile, flush=True)
        print(
            "  Effective controls: "
            + ", ".join(package["effective-policy.json"]["controls"]),
            flush=True,
        )
        print(
            "  Assessments: "
            + ", ".join(
                r["control_id"] + "=" + r["state"] for r in report["assessments"]
            ),
            flush=True,
        )
        print(
            "  Recommendation: " + report["decision"] + "; mutation permitted: false",
            flush=True,
        )
        print("  Official catalog/policy/evaluation schemas: passed", flush=True)
    unsafe = copy.deepcopy(baseline)
    unsafe["imports"]["catalogs"][0]["exclusions"].append("AM-REVIEW")
    unsafe["adherence"]["assessment-plans"] = [
        p
        for p in unsafe["adherence"]["assessment-plans"]
        if p["requirement-id"] != "AM-REVIEW-1"
    ]
    validate(unsafe, "Policy")
    print(
        "\n3. A policy removing Review is structurally valid under the official schema.",
        flush=True,
    )
    try:
        resolve_policy(catalog, unsafe)
    except InputError as exc:
        if str(exc) != "minimum_control_removed":
            raise
        print("   Custom resolver refuses it: minimum_control_removed.", flush=True)
    else:
        raise SystemExit("Unsafe policy unexpectedly accepted.")
    trace = execute(load(ROOT / "fixtures/satisfied.json"), "baseline")
    item = trace["evaluation.json"]["evaluations"][0]["assessment-logs"][0]
    print(
        "4. Trace one result: control AM-CI -> requirement AM-CI-1 -> evidence ci-unit.",
        flush=True,
    )
    print(
        "   Source content digest: " + item["evidence"][0]["source"]["digest"],
        flush=True,
    )
    print(
        "   Candidate, source policy, effective policy and evaluator version are retained.",
        flush=True,
    )
    print(
        "5. Same rules without Gemara give the same decision; Gemara adds artifact structure.",
        flush=True,
    )
    print(
        "Conclusion: schema validation, evaluation, trust verification and merge authority are separate.",
        flush=True,
    )


if __name__ == "__main__":
    main()
