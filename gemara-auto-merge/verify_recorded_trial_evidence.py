#!/usr/bin/env python3
"""Verify this lab's positive/negative live shadow example, without GitHub writes."""

import json
import os
from pathlib import Path

from github_pr_evidence import observe
from policy_evaluation import InputError, require


def verify():
    proof = []
    for number, expected in [(28, "eligible"), (29, "hold")]:
        report = observe(number)
        require(
            report["stable_during_collection"] and not report["api_errors"],
            "live_example_collection_incomplete",
        )
        require(
            report["candidate_decision"] == expected,
            "live_example_candidate_unexpected",
        )
        require(
            report["readiness_decision"] == "hold"
            and report["shadow"]["decision"] == "hold",
            "live_example_readiness_unexpected",
        )
        require(
            not report["mutation_permitted"] and not report["authorized_actions"],
            "live_example_authority_unexpected",
        )
        rows = report["shadow"]["evaluation"]["assessments"]
        if number == 28:
            require(
                all(row["state"] == "passed" for row in rows),
                "live_example_positive_incomplete",
            )
            require(
                report["evidence_details"]["AM-RISK"]["reason"]
                == "fullsend_lab_risk_receipt_verified",
                "live_example_risk_unverified",
            )
        else:
            require(
                any(row["id"] == "AM-CI" and row["state"] == "failed" for row in rows),
                "live_example_negative_not_detected",
            )
        proof.append(
            {
                "pr": number,
                "head_sha": report["head_sha"],
                "candidate": expected,
                "readiness": "hold",
                "combined_gate": "hold",
                "mutation_permitted": False,
            }
        )
    return {
        "example": "live-fullsend-gemara-shadow",
        "result": "passed",
        "production_readiness": "not_qualified",
        "observations": proof,
    }


def main():
    try:
        result = verify()
        print(json.dumps(result))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a") as stream:
                stream.write(
                    "\n## Live example verification: passed\n\nPR #28 passes every candidate assessment using a verified Fullsend risk receipt. PR #29 fails CI and is held. Repository readiness holds for both observations; neither result authorizes a merge.\n"
                )
        return 0
    except InputError as exc:
        print(
            json.dumps(
                {"result": "hold", "error": str(exc), "mutation_permitted": False}
            )
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "result": "hold",
                    "error": "live_example_verification_failed",
                    "mutation_permitted": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
