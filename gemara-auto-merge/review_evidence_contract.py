"""Consume a lab Review record with independently supplied publication proof.

This module does not establish that proof, fetch artifacts or grant merge rights.
The live observer continues using its existing verified host receipt until a
native publisher and authenticated retrieval path are separately demonstrated.
"""

from dataclasses import dataclass
import re

from fullsend_review_evidence import CATEGORIES, ID, SEVERITIES, STATUSES
from policy_evaluation import InputError, digest, require, utc

VERSION = "fullsend-review-evidence/v1"


@dataclass(frozen=True)
class PublicationProof:
    """Verifier-owned facts, not fields accepted from the evidence document."""

    subject: dict
    producer: dict
    payload_sha256: str
    run_status: str
    run_conclusion: str
    active: bool


def exact(value, keys):
    require(
        isinstance(value, dict) and set(value) == set(keys), "invalid_contract_shape"
    )


def sha(value, length):
    return isinstance(value, str) and re.fullmatch(
        "[a-f0-9]{" + str(length) + "}", value
    )


def validate(record):
    exact(
        record,
        [
            "schema_version",
            "subject",
            "producer",
            "issued_at",
            "completion",
            "review",
            "payload_sha256",
        ],
    )
    require(record["schema_version"] == VERSION, "unsupported_contract_version")
    s, p, r = record["subject"], record["producer"], record["review"]
    exact(
        s,
        [
            "repository_id",
            "repository",
            "pull_request",
            "head_sha",
            "base_sha",
            "configuration_sha",
        ],
    )
    require(
        s["repository"] == "fullsend-ai/auto-merge"
        and type(s["repository_id"]) is int
        and s["repository_id"] == 1383516376
        and type(s["pull_request"]) is int
        and 0 < s["pull_request"] < 1000000,
        "invalid_contract_subject",
    )
    require(
        all(sha(s[k], 40) for k in ["head_sha", "base_sha", "configuration_sha"]),
        "invalid_contract_subject",
    )
    exact(
        p,
        [
            "kind",
            "fullsend_commit",
            "overlay_sha256",
            "workflow_path",
            "run_id",
            "run_attempt",
        ],
    )
    require(
        p["kind"] == "fullsend-host-lab"
        and p["workflow_path"] == ".github/workflows/fullsend.yaml"
        and sha(p["fullsend_commit"], 40)
        and sha(p["overlay_sha256"], 64)
        and type(p["run_id"]) is int
        and 0 < p["run_id"] < 10**15
        and type(p["run_attempt"]) is int
        and 0 < p["run_attempt"] < 10**6,
        "invalid_contract_producer",
    )
    utc(record["issued_at"])
    require(
        record["completion"] in {"completed", "failed", "cancelled"},
        "invalid_contract_completion",
    )
    exact(r, ["action", "findings", "risk"])
    require(
        r["action"] in {"approve", "comment", "request-changes", "reject"}
        and isinstance(r["findings"], list)
        and len(r["findings"]) <= 500,
        "invalid_contract_review",
    )
    seen = set()
    for f in r["findings"]:
        exact(f, ["id", "severity", "category", "status"])
        require(
            isinstance(f["id"], str)
            and ID.fullmatch(f["id"])
            and f["id"] not in seen
            and f["severity"] in SEVERITIES
            and f["category"] in CATEGORIES
            and f["status"] in STATUSES,
            "invalid_contract_findings",
        )
        require(
            not (
                f["status"] == "dismissed_by_human"
                and f["severity"] in {"high", "critical"}
            ),
            "unsupported_contract_dismissal",
        )
        seen.add(f["id"])
    if r["risk"] is not None:
        risk = r["risk"]
        exact(risk, ["score", "level"])
        require(
            type(risk["score"]) is int
            and 1 <= risk["score"] <= 5
            and risk["level"]
            == ["low", "moderate", "elevated", "high", "critical"][risk["score"] - 1],
            "invalid_contract_risk",
        )
    require(
        sha(record["payload_sha256"], 64)
        and record["payload_sha256"]
        == digest({k: v for k, v in record.items() if k != "payload_sha256"}),
        "contract_integrity_mismatch",
    )


def consume(record, expected_subject, proof, as_of, maximum_age=600):
    """Return bounded assessment inputs. Unknown evidence never implies approval."""
    unknown = {"AM-REVIEW": None, "AM-FINDINGS": None, "AM-RISK": None}
    try:
        validate(record)
        require(isinstance(proof, PublicationProof), "contract_publication_unverified")
        require(
            record["subject"] == expected_subject == proof.subject,
            "contract_wrong_subject",
        )
        require(
            record["producer"] == proof.producer
            and record["payload_sha256"] == proof.payload_sha256,
            "contract_publication_mismatch",
        )
        require(
            proof.active is True
            and proof.run_status == "completed"
            and proof.run_conclusion == "success"
            and record["completion"] == "completed",
            "contract_incomplete_or_superseded",
        )
        require(
            type(maximum_age) is int
            and 0 < maximum_age <= 600
            and 0
            <= (utc(as_of) - utc(record["issued_at"])).total_seconds()
            <= maximum_age,
            "contract_stale_or_future",
        )
        review = record["review"]
        approved = review["action"] == "approve"
        clear = all(
            f["status"] in {"resolved_by_change", "dismissed_by_human"}
            for f in review["findings"]
        )
        return {
            "values": {
                "AM-REVIEW": approved,
                "AM-FINDINGS": approved and clear,
                "AM-RISK": review["risk"]["score"]
                if review["risk"] is not None
                else None,
            },
            "reason": "contract_verified",
            "payload_sha256": record["payload_sha256"],
            "merge_authority": False,
        }
    except (InputError, KeyError, TypeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, InputError) else "invalid_contract_shape"
        return {"values": unknown, "reason": reason, "merge_authority": False}


def test_report_evidence(counts, accepted_criteria=False):
    """A report can refute execution, but cannot self-certify test adequacy."""
    keys = {"tests", "passed", "failed", "skipped"}
    if (
        not isinstance(counts, dict)
        or set(counts) != keys
        or any(type(v) is not int or v < 0 for v in counts.values())
        or counts["tests"] != counts["passed"] + counts["failed"] + counts["skipped"]
    ):
        return {"value": None, "reason": "invalid_test_report"}
    if (
        counts["tests"] == 0
        or counts["passed"] == 0
        or counts["failed"]
        or counts["skipped"]
    ):
        return {
            "value": None,
            "reason": "test_execution_does_not_establish_sufficiency",
        }
    return {
        "value": True if accepted_criteria is True else None,
        "reason": "owner_criteria_satisfied"
        if accepted_criteria is True
        else "owner_test_criteria_unavailable",
    }
