"""Representative review-provider mappings; deliberately not live API adapters."""

from engine import InputError, candidate, fields, utc, validate_input


def normalize_review(source: dict) -> dict:
    fields(source, {"provenance", "format", "candidate", "collected_at", "review"})
    if source["provenance"] != "synthetic":
        raise InputError("synthetic_inputs_only")
    binding = candidate(source["candidate"])
    utc(source["collected_at"])
    if source["format"] == "fixture-provider-a/v1":
        review = fields(
            source["review"],
            {"verdict", "reviewer", "blocking_findings", "verified_fixture"},
        )
        decisions = {"APPROVE": "approved", "REJECT": "changes_requested"}
        if not isinstance(review["verdict"], str) or review["verdict"] not in decisions:
            raise InputError("unsupported_review_verdict")
        status, reviewer, findings = (
            decisions[review["verdict"]],
            review["reviewer"],
            review["blocking_findings"],
        )
    elif source["format"] == "fixture-provider-b/v1":
        review = fields(
            source["review"], {"result", "actor", "unresolved", "verified_fixture"}
        )
        unresolved = fields(review["unresolved"], {"blocking"})
        decisions = {"passed": "approved", "failed": "changes_requested"}
        if not isinstance(review["result"], str) or review["result"] not in decisions:
            raise InputError("unsupported_review_verdict")
        status, reviewer, findings = (
            decisions[review["result"]],
            review["actor"],
            unresolved["blocking"],
        )
    else:
        raise InputError("unsupported_provider_format")
    if type(review["verified_fixture"]) is not bool:
        raise InputError("invalid_fixture_verification")
    record = {
        "id": "review-adapted",
        "kind": "review",
        "subject": "independent-review",
        "status": status,
        "candidate": binding,
        "collected_at": source["collected_at"],
        "producer": "synthetic-review",
        "verification": "synthetic-trusted"
        if review["verified_fixture"]
        else "unverified",
        "reviewer_id": reviewer,
        "blocking_findings": findings,
    }
    validate_input(
        {
            "schema_version": "synthetic-evidence/v1",
            "provenance": "synthetic",
            "scenario": "provider-mapping",
            "evaluation_time": source["collected_at"],
            "candidate": binding,
            "records": [record],
        }
    )
    return record
