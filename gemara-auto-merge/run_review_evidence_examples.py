#!/usr/bin/env python3
"""Replay synthetic host records through the isolated Fullsend binary and Gemara."""

import copy
from dataclasses import replace
import hashlib
import json
import subprocess

from build_fullsend_evidence_lab import overlay_digest, SOURCE_COMMIT
from policy_evaluation import (
    ROOT,
    assess,
    digest,
    load,
    load_bundle,
    new_output,
    require,
    subject,
)
from review_evidence_contract import PublicationProof, consume

NOW = "2026-10-16T12:00:00Z"


def synthetic_input():
    return {
        "subject": {
            "repository_id": 1383516376,
            "repository": "fullsend-ai/auto-merge",
            "pull_request": 999001,
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "configuration_sha": "b" * 40,
        },
        "producer": {
            "kind": "fullsend-host-lab",
            "fullsend_commit": SOURCE_COMMIT,
            "overlay_sha256": overlay_digest(),
            "workflow_path": ".github/workflows/fullsend.yaml",
            "run_id": 1234,
            "run_attempt": 1,
        },
        "issued_at": NOW,
        "completion": "completed",
        "review": {
            "action": "approve",
            "findings": [],
            "risk": {"score": 1, "level": "low"},
        },
    }


def synthetic_proof(record):
    return PublicationProof(
        copy.deepcopy(record["subject"]),
        copy.deepcopy(record["producer"]),
        record["payload_sha256"],
        "completed",
        "success",
        True,
    )


def gemara_case(record, expected, proof, as_of=NOW):
    consumed = consume(record, expected, proof, as_of)
    who = subject(
        repository="fullsend-ai/auto-merge",
        configuration=digest(expected),
        candidate=True,
    )
    who.update(head_sha=expected["head_sha"], base_sha=expected["base_sha"])
    values = {
        "AM-CI": True,
        "AM-CLASS": "documentation",
        "AM-PROTECTED": True,
        **consumed["values"],
    }
    observations = {
        k: {
            "subject_sha256": digest(who),
            "collected_at": as_of,
            "trusted_source": True,
            "value": v,
        }
        for k, v in values.items()
        if v is not None
    }
    result = assess(load_bundle(), "candidate", who, observations, as_of)
    return consumed, result


def run():
    receipt = load(ROOT / "out/fullsend-evidence-build.json")
    binary = ROOT.parent / ".fullsend/bin/fullsend"
    require(
        binary.is_file()
        and not binary.is_symlink()
        and receipt["source_commit"] == SOURCE_COMMIT
        and receipt["overlay_sha256"] == overlay_digest()
        and hashlib.sha256(binary.read_bytes()).hexdigest() == receipt["binary_sha256"],
        "evidence_build_required",
    )
    child = subprocess.run(
        [str(binary), "review-evidence-lab"],
        input=json.dumps(synthetic_input()),
        text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        timeout=30,
    )
    require(
        child.returncode == 0 and len(child.stdout) < 128 * 1024,
        "evidence_producer_failed",
    )
    record = json.loads(child.stdout)
    proof = synthetic_proof(record)
    cases = [("valid", record, record["subject"], proof, NOW, "eligible")]
    altered = copy.deepcopy(record)
    altered["review"]["action"] = "reject"
    forged = dict(
        altered,
        payload_sha256=digest(
            {k: v for k, v in altered.items() if k != "payload_sha256"}
        ),
    )
    cases += [
        (
            "wrong-head",
            record,
            dict(record["subject"], head_sha="f" * 40),
            proof,
            NOW,
            "hold",
        ),
        (
            "wrong-configuration",
            record,
            dict(record["subject"], configuration_sha="f" * 40),
            proof,
            NOW,
            "hold",
        ),
        ("unverified", record, record["subject"], None, NOW, "hold"),
        ("altered", altered, record["subject"], proof, NOW, "hold"),
        ("forged-self-digest", forged, record["subject"], proof, NOW, "hold"),
        ("stale", record, record["subject"], proof, "2026-10-16T12:10:01Z", "hold"),
        ("future", record, record["subject"], proof, "2026-10-16T11:59:59Z", "hold"),
        (
            "superseded",
            record,
            record["subject"],
            replace(proof, active=False),
            NOW,
            "hold",
        ),
        (
            "cancelled-run",
            record,
            record["subject"],
            replace(proof, run_conclusion="cancelled"),
            NOW,
            "hold",
        ),
        (
            "wrong-attempt",
            record,
            record["subject"],
            replace(proof, producer=dict(proof.producer, run_attempt=2)),
            NOW,
            "hold",
        ),
    ]
    for name, changes in [
        (
            "open-finding",
            {
                "findings": [
                    {
                        "id": "f_one",
                        "severity": "low",
                        "category": "logic-error",
                        "status": "open",
                    }
                ]
            },
        ),
        ("high-risk", {"risk": {"score": 5, "level": "critical"}}),
        ("missing-risk", {"risk": None}),
        ("review-rejected", {"action": "reject"}),
    ]:
        changed = copy.deepcopy(record)
        changed["review"].update(changes)
        changed["payload_sha256"] = digest(
            {k: v for k, v in changed.items() if k != "payload_sha256"}
        )
        cases.append(
            (name, changed, changed["subject"], synthetic_proof(changed), NOW, "hold")
        )
    destination = new_output("contract")
    rows = []
    for name, value, expected, publication, as_of, decision in cases:
        consumed, result = gemara_case(value, expected, publication, as_of)
        require(result["decision"] == decision, "contract_replay_mismatch")
        (destination / (name + "-evaluation-log.json")).write_text(
            json.dumps(result["evaluation_log"], indent=2) + "\n"
        )
        rows.append(
            {
                "case": name,
                "decision": result["decision"],
                "reason": consumed["reason"],
                "assessments": result["assessments"],
                "merge_authority": False,
            }
        )
    (destination / "synthetic-review-evidence.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    (destination / "results.json").write_text(
        json.dumps(
            {
                "provenance": "synthetic-host-input-and-publication-proof-real-fullsend-binary-and-gemara",
                "build": receipt,
                "cases": rows,
                "production_publication_demonstrated": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "cases": len(rows),
                "all_expected_results": True,
                "native_fullsend_binary": True,
                "synthetic_inputs_and_publication_proof": True,
                "merge_authority": False,
                "output": str(destination.relative_to(ROOT)),
            }
        )
    )
    return destination


if __name__ == "__main__":
    run()
