import copy
from dataclasses import replace
import unittest

from policy_evaluation import digest
from review_evidence_contract import consume, test_report_evidence
from run_review_evidence_examples import (
    NOW,
    gemara_case,
    synthetic_input,
    synthetic_proof,
)


def fixture():
    record = dict(synthetic_input(), schema_version="fullsend-review-evidence/v1")
    record["payload_sha256"] = digest(record)
    return record


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.record = fixture()
        self.proof = synthetic_proof(self.record)

    def check(self, record=None, proof=None, subject=None, now=NOW):
        return consume(
            self.record if record is None else record,
            self.record["subject"] if subject is None else subject,
            self.proof if proof is None else proof,
            now,
        )

    def test_valid_producer_record_does_not_grant_merge_authority(self):
        result = self.check()
        self.assertEqual(
            result["values"], {"AM-REVIEW": True, "AM-FINDINGS": True, "AM-RISK": 1}
        )
        self.assertFalse(result["merge_authority"])

    def test_self_asserted_trust_and_recomputed_digest_are_not_publication_proof(self):
        value = copy.deepcopy(self.record)
        value["review"]["risk"] = {"score": 5, "level": "critical"}
        value["payload_sha256"] = digest(
            {k: v for k, v in value.items() if k != "payload_sha256"}
        )
        self.assertEqual(self.check(value)["reason"], "contract_publication_mismatch")
        self.assertEqual(
            consume(value, value["subject"], {"trusted": True}, NOW)["reason"],
            "contract_publication_unverified",
        )

    def test_missing_malformed_unknown_version_and_extra_fields_hold(self):
        variants = [
            None,
            {},
            dict(self.record, schema_version="future"),
            dict(self.record, trusted=True),
            dict(self.record, review={}),
            dict(self.record, payload_sha256="f" * 64),
        ]
        for value in variants:
            with self.subTest(value=type(value).__name__):
                result = consume(value, self.record["subject"], self.proof, NOW)
                self.assertTrue(all(x is None for x in result["values"].values()))

    def test_context_run_attempt_and_subject_drift_hold(self):
        for key, value in [
            ("head_sha", "f" * 40),
            ("base_sha", "f" * 40),
            ("configuration_sha", "f" * 40),
            ("pull_request", 999002),
            ("repository_id", 1),
        ]:
            self.assertEqual(
                self.check(subject=dict(self.record["subject"], **{key: value}))[
                    "reason"
                ],
                "contract_wrong_subject",
            )
        for proof in [
            replace(self.proof, active=False),
            replace(self.proof, run_status="in_progress"),
            replace(self.proof, run_conclusion="failure"),
            replace(self.proof, producer=dict(self.proof.producer, run_attempt=2)),
        ]:
            self.assertIsNone(self.check(proof=proof)["values"]["AM-FINDINGS"])

    def test_stale_future_and_invalid_freshness_limit_hold(self):
        for now in ["2026-10-16T12:10:01Z", "2026-10-16T11:59:59Z"]:
            self.assertEqual(self.check(now=now)["reason"], "contract_stale_or_future")
        for age in [True, 0, 601]:
            self.assertIsNone(
                consume(self.record, self.record["subject"], self.proof, NOW, age)[
                    "values"
                ]["AM-RISK"]
            )

    def test_open_or_unsupported_finding_cannot_disappear_into_approval(self):
        for status in ["open", "reclassified", "dismissed_by_human"]:
            value = copy.deepcopy(self.record)
            value["review"]["findings"] = [
                {
                    "id": "f_one",
                    "severity": "high",
                    "category": "logic-error",
                    "status": status,
                }
            ]
            value["payload_sha256"] = digest(
                {k: v for k, v in value.items() if k != "payload_sha256"}
            )
            result = self.check(value, proof=synthetic_proof(value))
            self.assertIsNot(result["values"]["AM-FINDINGS"], True)

    def test_verified_authentic_high_risk_still_fails_native_gemara(self):
        value = copy.deepcopy(self.record)
        value["review"]["risk"] = {"score": 5, "level": "critical"}
        value["payload_sha256"] = digest(
            {k: v for k, v in value.items() if k != "payload_sha256"}
        )
        consumed, result = gemara_case(value, value["subject"], synthetic_proof(value))
        self.assertEqual(consumed["reason"], "contract_verified")
        self.assertEqual(result["decision"], "hold")
        self.assertIn(
            "failed",
            [r["state"] for r in result["assessments"] if r["id"] == "AM-RISK"],
        )

    def test_skipped_empty_or_failed_tests_do_not_establish_readiness(self):
        for counts in [
            {"tests": 0, "passed": 0, "failed": 0, "skipped": 0},
            {"tests": 3, "passed": 0, "failed": 0, "skipped": 3},
            {"tests": 3, "passed": 2, "failed": 0, "skipped": 1},
            {"tests": 3, "passed": 2, "failed": 1, "skipped": 0},
        ]:
            self.assertIsNone(test_report_evidence(counts, True)["value"])
        good = {"tests": 3, "passed": 3, "failed": 0, "skipped": 0}
        self.assertIsNone(test_report_evidence(good)["value"])
        self.assertTrue(test_report_evidence(good, True)["value"])
