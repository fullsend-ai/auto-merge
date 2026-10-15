#!/usr/bin/env python3
"""Replay native Gemara policy cases. Evidence is synthetic; no forge/model calls."""

import argparse
import copy
import json
from platform_lab import load_bundle, subject, digest, qualification, gate, new_output

NOW = "2026-10-14T18:00:00Z"


def synthetic(bundle, who, purpose):
    defaults = {"AM-RISK": 1, "AM-CLASS": "documentation"}
    return {
        control["id"]: {
            "subject_sha256": digest(who),
            "collected_at": NOW,
            "trusted_source": True,
            "value": defaults.get(control["id"], True),
        }
        for catalog in bundle["catalogs"].values()
        for control in catalog["controls"]
        if purpose in control["assessment-requirements"][0]["applicability"]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    bundle = load_bundle()
    who = subject(repository="fullsend-ai/auto-merge", candidate=True)
    ready = {k: v for k, v in who.items() if k not in {"head_sha", "base_sha"}}
    receipt = qualification(bundle, ready, NOW, synthetic(bundle, ready, "readiness"))
    baseline = synthetic(bundle, who, "candidate")
    cases = []
    for case in [
        "satisfied",
        "failed-ci",
        "missing-review",
        "stale-review",
        "wrong-revision",
        "repository-policy",
    ]:
        obs = copy.deepcopy(baseline)
        if case == "failed-ci":
            obs["AM-CI"]["value"] = False
        if case == "missing-review":
            del obs["AM-REVIEW"]
        if case == "stale-review":
            obs["AM-REVIEW"]["collected_at"] = "2026-10-14T17:00:00Z"
        if case == "wrong-revision":
            obs["AM-REVIEW"]["subject_sha256"] = "0" * 64
        if case == "repository-policy":
            obs["AM-CLASS"]["value"] = "dependency-digest"
        result = gate(bundle, who, NOW, obs, "shadow", receipt)
        expected = "would_allow" if case == "satisfied" else "hold"
        if result["decision"] != expected or result["mutation_permitted"]:
            raise SystemExit("Native-policy scenario failed: " + case)
        cases.append({"case": case, "result": result})
    modes = {
        mode: gate(bundle, who, NOW, baseline, mode, receipt)["decision"]
        for mode in ["off", "shadow", "light", "gemara"]
    }
    report = {
        "synthetic_evidence": True,
        "engine": "gemara",
        "cases": cases,
        "modes": modes,
        "mutation_permitted": False,
    }
    if args.write_report:
        destination = new_output("synthetic")
        (destination / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "synthetic_evidence": True,
                "cases": {x["case"]: x["result"]["decision"] for x in cases},
                "modes": modes,
                "mutation_permitted": False,
            }
        )
    )


if __name__ == "__main__":
    main()
