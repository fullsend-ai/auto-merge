#!/usr/bin/env python3
"""Walk through every required scenario and conservative evidence edge case."""

from pathlib import Path
from datetime import datetime, timezone
import json

from run import execute, load, write_output

ROOT = Path(__file__).resolve().parent
CASES = [
    ("satisfied", "baseline", "eligible_for_demo_only"),
    ("failed-ci", "baseline", "hold"),
    ("missing-review", "baseline", "hold"),
    ("stale-review", "baseline", "hold"),
    ("repository-failed", "baseline", "eligible_for_demo_only"),
    ("repository-failed", "repository", "hold"),
    ("repository-satisfied", "repository", "eligible_for_demo_only"),
    ("untrusted-review", "baseline", "hold"),
    ("conflicting-ci", "baseline", "hold"),
    ("unsupported-ci", "baseline", "hold"),
    ("future-evidence", "baseline", "hold"),
    ("cross-repository", "baseline", "hold"),
    ("gitlab-provider", "baseline", "eligible_for_demo_only"),
]


def main() -> None:
    group = datetime.now(timezone.utc).strftime("demo-%Y%m%dT%H%M%S%fZ")
    root = ROOT / "out" / group
    results = []
    print(
        "Inputs are synthetic. Evaluation is custom code. CUE validates official schemas. No model or forge action runs."
    )
    for scenario, profile, expected in CASES:
        package = execute(load(ROOT / "fixtures" / (scenario + ".json")), profile)
        report = package["recommendation.json"]
        if report["decision"] != expected:
            raise SystemExit(
                "Unexpected scenario result; no merge action is available."
            )
        destination = root / (scenario + "-" + profile)
        write_output(package, destination)
        print(scenario + " / " + profile + ": " + report["decision"])
        results.append(
            {
                "scenario": scenario,
                "profile": profile,
                "decision": report["decision"],
                "states": {r["control_id"]: r["state"] for r in report["assessments"]},
                "comparison": package["comparison.json"],
                "path": str(destination.relative_to(ROOT)),
            }
        )
    (root / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Walkthrough outputs: " + str(root.relative_to(ROOT)))


if __name__ == "__main__":
    main()
