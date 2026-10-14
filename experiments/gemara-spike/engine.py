"""Pure, conservative evaluation of explicitly synthetic normalized evidence."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re

VERSION = "0.1.0"
MINIMUM_CONTROLS = frozenset({"AM-CI", "AM-REVIEW"})
CONTROL_RULES = {
    "AM-CI": ("ci", "unit"),
    "AM-REVIEW": ("review", "independent-review"),
    "AM-REPO": ("repository", "security-scan"),
}
STATUSES = {
    "passed",
    "failed",
    "approved",
    "changes_requested",
    "skipped",
    "neutral",
    "unknown",
}
EVIDENCE_FIELDS = {
    "id",
    "kind",
    "subject",
    "status",
    "candidate",
    "collected_at",
    "producer",
    "verification",
}
CANDIDATE_FIELDS = {
    "forge",
    "repository",
    "number",
    "head_sha",
    "base_ref",
    "author_id",
}
PRODUCERS = {
    "ci": "synthetic-ci",
    "review": "synthetic-review",
    "repository": "synthetic-ci",
}
GEMARA_RESULTS = {
    "passed": "Passed",
    "failed": "Failed",
    "missing": "Unknown",
    "stale": "Unknown",
    "untrusted": "Unknown",
    "conflicting": "Needs Review",
    "unsupported": "Unknown",
    "unknown": "Unknown",
}


class InputError(ValueError):
    """Stable codes only: never echo a rejected value or environment content."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise InputError("invalid_timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("invalid_timestamp") from exc


def fields(value: object, required: set[str], optional: set[str] = frozenset()) -> dict:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise InputError("invalid_fields")
    return value


def identifier(value: object, pattern: str = r"[a-z][a-z0-9-]{0,39}") -> None:
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise InputError("invalid_identifier")


def candidate(value: object) -> dict:
    value = fields(value, CANDIDATE_FIELDS)
    if not isinstance(value["forge"], str) or value["forge"] not in {
        "github",
        "gitlab",
    }:
        raise InputError("unsupported_forge")
    identifier(value["repository"], r"example/[a-z0-9-]{1,40}")
    if type(value["number"]) is not int or not 1 <= value["number"] <= 999:
        raise InputError("invalid_candidate_number")
    identifier(value["head_sha"], r"[a-f0-9]{40}")
    if value["base_ref"] != "main":
        raise InputError("unsupported_base")
    identifier(value["author_id"], r"fixture-[a-z0-9-]{1,30}")
    return value


def validate_input(value: object) -> dict:
    value = fields(
        value,
        {
            "schema_version",
            "provenance",
            "scenario",
            "evaluation_time",
            "candidate",
            "records",
        },
    )
    if (
        value["schema_version"] != "synthetic-evidence/v1"
        or value["provenance"] != "synthetic"
    ):
        raise InputError("synthetic_inputs_only")
    identifier(value["scenario"])
    utc(value["evaluation_time"])
    candidate(value["candidate"])
    if not isinstance(value["records"], list) or len(value["records"]) > 50:
        raise InputError("invalid_record_count")
    seen = set()
    for record in value["records"]:
        kind = record.get("kind") if isinstance(record, dict) else None
        if not isinstance(kind, str) or kind not in PRODUCERS:
            raise InputError("unsupported_evidence_kind")
        required = EVIDENCE_FIELDS | (
            {"reviewer_id", "blocking_findings"} if kind == "review" else set()
        )
        fields(record, required)
        identifier(record["id"])
        if record["id"] in seen:
            raise InputError("duplicate_evidence_id")
        seen.add(record["id"])
        if not isinstance(record["subject"], str) or record["subject"] not in {
            "unit",
            "independent-review",
            "security-scan",
        }:
            raise InputError("unsupported_subject")
        if (
            not isinstance(record["status"], str)
            or record["status"] not in STATUSES
            or not isinstance(record["verification"], str)
            or record["verification"]
            not in {"synthetic-trusted", "unverified", "unknown"}
        ):
            raise InputError("invalid_evidence_status")
        identifier(record["producer"])
        candidate(record["candidate"])
        utc(record["collected_at"])
        if kind == "review":
            identifier(record["reviewer_id"], r"fixture-[a-z0-9-]{1,30}")
            if (
                type(record["blocking_findings"]) is not int
                or not 0 <= record["blocking_findings"] <= 100
            ):
                raise InputError("invalid_findings_count")
    return value


def resolve_policy(catalog: dict, policy: dict) -> dict:
    """This resolution and floor are demo code, not a Gemara-provided policy engine."""
    try:
        if policy["scope"] != {
            "in": {"technologies": ["synthetic-auto-merge-fixture"]}
        }:
            raise InputError("unsupported_scope")
        controls = catalog["controls"]
        ids = [c["id"] for c in controls]
        if len(ids) != len(set(ids)) or not set(ids) <= CONTROL_RULES.keys():
            raise InputError("invalid_catalog_controls")
        imports = policy["imports"]["catalogs"]
        if len(imports) != 1 or imports[0]["reference-id"] != catalog["metadata"]["id"]:
            raise InputError("unsupported_catalog_import")
        item = imports[0]
        if set(item) - {"reference-id", "exclusions"}:
            raise InputError("unsupported_override")
        exclusions = item.get("exclusions", [])
        if (
            not isinstance(exclusions, list)
            or len(exclusions) != len(set(exclusions))
            or not set(exclusions) <= set(ids)
        ):
            raise InputError("invalid_exclusions")
        selected = [c for c in controls if c["id"] not in exclusions]
        if not MINIMUM_CONTROLS <= {c["id"] for c in selected}:
            raise InputError("minimum_control_removed")
        if any(
            c.get("state") != "Active"
            or any(r.get("state") != "Active" for r in c["assessment-requirements"])
            for c in selected
        ):
            raise InputError("inactive_requirement")
        requirements = [r["id"] for c in selected for r in c["assessment-requirements"]]
        if requirements != [c["id"] + "-1" for c in selected]:
            raise InputError("unsupported_requirement")
        plans = policy["adherence"]["assessment-plans"]
        if len(plans) != len(requirements) or {
            p["requirement-id"] for p in plans
        } != set(requirements):
            raise InputError("assessment_plan_mismatch")
        if len({p["id"] for p in plans}) != len(plans):
            raise InputError("duplicate_plan_id")
        for plan in plans:
            methods = plan["evaluation-methods"]
            if len(methods) != 1 or methods[0] != {
                "id": "local-python",
                "type": "Intent",
                "mode": "Automated",
                "required": True,
            }:
                raise InputError("unsupported_evaluation_method")
        return {
            "schema_version": "effective-policy/v1",
            "catalog_id": catalog["metadata"]["id"],
            "policy_id": policy["metadata"]["id"],
            "catalog_sha256": digest(catalog),
            "policy_sha256": digest(policy),
            "controls": [c["id"] for c in selected],
            "minimum_controls": sorted(MINIMUM_CONTROLS),
            "maximum_age_seconds": 600,
            "trust_domain": "synthetic-only",
            "evaluator_version": VERSION,
            "mutation_permitted": False,
        }
    except (KeyError, TypeError) as exc:
        raise InputError("invalid_policy_structure") from exc


def assessment(control: str, evidence: dict, effective: dict) -> dict:
    kind, subject = CONTROL_RULES[control]
    records = [
        r for r in evidence["records"] if (r["kind"], r["subject"]) == (kind, subject)
    ]
    states = []
    now = utc(evidence["evaluation_time"])
    if not records:
        states.append("missing")
    for record in records:
        if record["candidate"] != evidence["candidate"]:
            states.append("stale")
        age = (now - utc(record["collected_at"])).total_seconds()
        if age < 0:
            states.append("unknown")
        elif age > effective["maximum_age_seconds"]:
            states.append("stale")
        if (
            record["producer"] != PRODUCERS[kind]
            or record["verification"] != "synthetic-trusted"
        ):
            states.append("untrusted")
        if kind == "review":
            if record["reviewer_id"] == evidence["candidate"]["author_id"]:
                states.append("failed")
            if record["blocking_findings"]:
                states.append("failed")
        passing = "approved" if kind == "review" else "passed"
        failing = "changes_requested" if kind == "review" else "failed"
        if record["status"] == failing:
            states.append("failed")
        elif record["status"] != passing:
            states.append(
                "unsupported"
                if record["status"] in {"skipped", "neutral"}
                else "unknown"
            )
    if len({r["status"] for r in records}) > 1:
        states.append("conflicting")
    # All reasons are retained; a valid sibling record never erases an invalid one.
    reasons = sorted(set(states))
    result = next(
        (
            s
            for s in [
                "conflicting",
                "failed",
                "untrusted",
                "stale",
                "missing",
                "unsupported",
                "unknown",
            ]
            if s in states
        ),
        "passed",
    )
    return {
        "control_id": control,
        "requirement_id": control + "-1",
        "state": result,
        "reasons": reasons,
        "evidence_ids": [r["id"] for r in records],
    }


def validate_effective(effective: dict) -> None:
    fields(
        effective,
        {
            "schema_version",
            "catalog_id",
            "policy_id",
            "catalog_sha256",
            "policy_sha256",
            "controls",
            "minimum_controls",
            "maximum_age_seconds",
            "trust_domain",
            "evaluator_version",
            "mutation_permitted",
        },
    )
    if (
        effective["schema_version"] != "effective-policy/v1"
        or effective["trust_domain"] != "synthetic-only"
        or effective["mutation_permitted"] is not False
    ):
        raise InputError("invalid_effective_policy")
    controls = effective["controls"]
    if (
        not isinstance(controls, list)
        or not all(isinstance(c, str) for c in controls)
        or len(controls) != len(set(controls))
        or not set(controls) <= CONTROL_RULES.keys()
        or not MINIMUM_CONTROLS <= set(controls)
    ):
        raise InputError("invalid_effective_controls")
    if (
        effective["minimum_controls"] != sorted(MINIMUM_CONTROLS)
        or type(effective["maximum_age_seconds"]) is not int
        or not 0 < effective["maximum_age_seconds"] <= 600
    ):
        raise InputError("invalid_effective_floor")
    for key in ["catalog_sha256", "policy_sha256"]:
        identifier(effective[key], r"[a-f0-9]{64}")
    for key in ["catalog_id", "policy_id"]:
        identifier(effective[key])
    if effective["evaluator_version"] != VERSION:
        raise InputError("unsupported_evaluator_version")


def evaluate(evidence: dict, effective: dict) -> dict:
    validate_input(evidence)
    validate_effective(effective)
    rows = [assessment(c, evidence, effective) for c in effective["controls"]]
    return {
        "schema_version": "demo-recommendation/v1",
        "scenario": evidence["scenario"],
        "decision": "eligible_for_demo_only"
        if all(r["state"] == "passed" for r in rows)
        else "hold",
        "candidate": evidence["candidate"],
        "evaluation_as_of": evidence["evaluation_time"],
        "effective_policy_sha256": digest(effective),
        "evidence_sha256": digest(evidence),
        "evaluator": {
            "name": "custom-offline-python",
            "version": VERSION,
            "llm_used": False,
        },
        "provenance": "synthetic",
        "mutation_permitted": False,
        "authorized_actions": [],
        "assessments": rows,
    }


def gemara_log(
    catalog: dict, policy: dict, evidence: dict, report: dict, started: str, ended: str
) -> dict:
    refs = [
        {
            "id": "demo-controls",
            "title": catalog["title"],
            "version": "0.1.0",
            "url": "urn:gemara-spike:catalog:" + digest(catalog),
        },
        {
            "id": policy["metadata"]["id"],
            "title": policy["title"],
            "version": "0.1.0",
            "url": "urn:gemara-spike:policy:" + digest(policy),
        },
        {
            "id": "demo-evidence",
            "title": "Synthetic normalized input",
            "version": "1",
            "url": "urn:sha256:" + digest(evidence),
        },
    ]
    rows = []
    for item in report["assessments"]:
        control = next(c for c in catalog["controls"] if c["id"] == item["control_id"])
        records = [r for r in evidence["records"] if r["id"] in item["evidence_ids"]]
        message = "synthetic-only; " + (
            ", ".join(item["reasons"])
            if item["reasons"]
            else "requirements satisfied in fixture"
        )
        result = GEMARA_RESULTS[item["state"]]
        log = {
            "requirement": {
                "reference-id": "demo-controls",
                "entry-id": item["requirement_id"],
            },
            "plan": {
                "reference-id": policy["metadata"]["id"],
                "entry-id": next(
                    p["id"]
                    for p in policy["adherence"]["assessment-plans"]
                    if p["requirement-id"] == item["requirement_id"]
                ),
            },
            "description": "Custom deterministic assessment of synthetic input, not live verification.",
            "result": result,
            "message": message,
            "applicability": ["synthetic-pr"],
            "steps": [
                "check binding, logical freshness, fixture trust, result and independence"
            ],
            "steps-executed": 1,
            "start": started,
            "end": ended,
        }
        if records:
            log["evidence"] = [
                {
                    "id": r["id"],
                    "type": "synthetic-normalized-evidence",
                    "collected-at": r["collected_at"],
                    "payload": r,
                    "source": {
                        "reference-id": "demo-evidence",
                        "coordinate": "records/" + r["id"],
                        "digest": "sha256:" + digest(r),
                    },
                    "description": "Synthetic fixture. This trust label is not a production authentication mechanism.",
                }
                for r in records
            ]
        rows.append(
            {
                "name": control["title"],
                "result": result,
                "message": message,
                "control": {
                    "reference-id": "demo-controls",
                    "entry-id": item["control_id"],
                },
                "assessment-logs": [log],
            }
        )
    result = (
        "Passed"
        if report["decision"] == "eligible_for_demo_only"
        else (
            "Failed"
            if any(x["state"] == "failed" for x in report["assessments"])
            else "Needs Review"
        )
    )
    return {
        "metadata": {
            "id": "evaluation-" + evidence["scenario"],
            "type": "EvaluationLog",
            "gemara-version": "1.6.0",
            "version": VERSION,
            "date": ended,
            "description": "Local synthetic policy evaluation. No merge authority. Evidence freshness uses the fixture evaluation_as_of value.",
            "author": {
                "id": "demo-evaluator",
                "name": "Custom offline evaluator",
                "type": "Software",
                "version": VERSION,
            },
            "mapping-references": refs,
        },
        "target": {
            "id": "candidate-" + evidence["candidate"]["head_sha"],
            "name": "Synthetic candidate",
            "type": "Software",
            "version": evidence["candidate"]["head_sha"],
            "uri": "urn:gemara-spike:candidate:" + digest(evidence["candidate"]),
            "environment": "local-fixture",
        },
        "result": result,
        "evaluations": rows,
    }
