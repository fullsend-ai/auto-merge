"""Safety and semantic boundaries, not a second implementation of the evaluator."""

from pathlib import Path
from unittest import mock
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from adapters import normalize_review
from engine import InputError, digest, evaluate, resolve_policy, validate_input
from run import ROOT, execute, load, write_output
from validate import ValidationError, validate


class EvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = load(ROOT / "fixtures/satisfied.json")
        self.catalog = load(ROOT / "catalog.json")
        self.policy = load(ROOT / "policies/baseline.json")
        self.effective = resolve_policy(self.catalog, self.policy)

    def decision(self, value):
        return evaluate(value, self.effective)

    def test_provider_mapping_preserves_revision_and_independence(self):
        for name in ["a", "b"]:
            source = load(ROOT / "fixtures" / ("provider-" + name + ".json"))
            record = normalize_review(source)
            value = copy.deepcopy(self.base)
            value["records"][1] = record
            self.assertEqual(self.decision(value)["decision"], "eligible_for_demo_only")
            source["review"]["verified_fixture"] = False
            value["records"][1] = normalize_review(source)
            self.assertEqual(self.decision(value)["decision"], "hold")

    def test_forged_effective_policy_cannot_create_an_empty_pass(self):
        for key, value in [
            ("controls", []),
            ("maximum_age_seconds", 3600),
            ("mutation_permitted", True),
            ("minimum_controls", []),
        ]:
            effective = copy.deepcopy(self.effective)
            effective[key] = value
            with self.assertRaises(InputError):
                evaluate(self.base, effective)

    def test_required_scenarios(self):
        expected = {
            "satisfied": "eligible_for_demo_only",
            "failed-ci": "hold",
            "missing-review": "hold",
            "stale-review": "hold",
        }
        for name, result in expected.items():
            with self.subTest(name=name):
                report = self.decision(load(ROOT / "fixtures" / (name + ".json")))
                self.assertEqual(report["decision"], result)
                self.assertFalse(report["mutation_permitted"])
                self.assertEqual(report["authorized_actions"], [])

    def test_repository_policy_changes_same_evidence(self):
        evidence = load(ROOT / "fixtures/repository-failed.json")
        baseline = evaluate(evidence, self.effective)
        repo = resolve_policy(self.catalog, load(ROOT / "policies/repository.json"))
        tightened = evaluate(evidence, repo)
        self.assertEqual(baseline["decision"], "eligible_for_demo_only")
        self.assertEqual(tightened["decision"], "hold")
        self.assertNotEqual(
            baseline["effective_policy_sha256"], tightened["effective_policy_sha256"]
        )

    def test_every_candidate_identity_field_is_bound(self):
        replacements = {
            "forge": "gitlab",
            "repository": "example/other",
            "number": 2,
            "head_sha": "b" * 40,
            "base_ref": "main",
            "author_id": "fixture-other",
        }
        for field, replacement in replacements.items():
            if replacement == self.base["candidate"][field]:
                continue
            with self.subTest(field=field):
                value = copy.deepcopy(self.base)
                value["records"][1]["candidate"][field] = replacement
                report = self.decision(value)
                self.assertEqual(report["decision"], "hold")
                self.assertIn("stale", report["assessments"][1]["reasons"])

    def test_old_or_future_timestamp_never_passes(self):
        for timestamp in ["2026-10-14T11:00:00Z", "2026-10-14T13:00:00Z"]:
            value = copy.deepcopy(self.base)
            value["records"][0]["collected_at"] = timestamp
            self.assertEqual(self.decision(value)["decision"], "hold")

    def test_untrusted_provider_or_assertion_never_passes(self):
        for key, replacement in [
            ("producer", "unrecognized-provider"),
            ("verification", "unverified"),
        ]:
            value = copy.deepcopy(self.base)
            value["records"][1][key] = replacement
            self.assertEqual(
                self.decision(value)["assessments"][1]["state"], "untrusted"
            )

    def test_author_cannot_supply_independent_review(self):
        value = copy.deepcopy(self.base)
        value["records"][1]["reviewer_id"] = value["candidate"]["author_id"]
        self.assertEqual(self.decision(value)["decision"], "hold")

    def test_open_findings_block_even_with_approval(self):
        value = copy.deepcopy(self.base)
        value["records"][1]["blocking_findings"] = 1
        self.assertEqual(self.decision(value)["decision"], "hold")

    def test_conflict_is_retained_not_overwritten_by_pass(self):
        report = self.decision(load(ROOT / "fixtures/conflicting-ci.json"))
        self.assertEqual(report["assessments"][0]["state"], "conflicting")
        self.assertIn("failed", report["assessments"][0]["reasons"])
        self.assertEqual(report["decision"], "hold")

    def test_skipped_neutral_and_unknown_are_not_passed_execution(self):
        for status in ["skipped", "neutral", "unknown"]:
            value = copy.deepcopy(self.base)
            value["records"][0]["status"] = status
            self.assertEqual(self.decision(value)["decision"], "hold")

    def test_cross_forge_fixture_uses_same_contract_not_live_auth(self):
        report = self.decision(load(ROOT / "fixtures/gitlab-provider.json"))
        self.assertEqual(report["decision"], "eligible_for_demo_only")
        self.assertFalse(report["mutation_permitted"])

    def test_extra_fields_real_data_and_wrong_types_rejected(self):
        modifications = [
            lambda x: x.update({"secret": "SYNTHETIC_SECRET_SENTINEL"}),
            lambda x: x.update({"provenance": "live"}),
            lambda x: x["candidate"].update({"number": True}),
            lambda x: x["records"][0].update({"kind": []}),
            lambda x: x["records"][0].update({"status": {}}),
        ]
        for change in modifications:
            value = copy.deepcopy(self.base)
            change(value)
            with self.assertRaises(InputError):
                validate_input(value)

    def test_duplicate_evidence_ids_and_json_keys_rejected(self):
        value = copy.deepcopy(self.base)
        value["records"].append(copy.deepcopy(value["records"][0]))
        with self.assertRaisesRegex(InputError, "duplicate_evidence_id"):
            self.decision(value)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text('{"provenance":"live","provenance":"synthetic"}')
            with self.assertRaisesRegex(InputError, "duplicate_json_key"):
                load(path)

    def test_freshness_limit_is_explicit_and_not_inferred_from_now(self):
        self.assertEqual(self.effective["maximum_age_seconds"], 600)
        self.assertEqual(
            self.decision(self.base)["evaluation_as_of"], "2026-10-14T12:01:00Z"
        )

    def test_policy_cannot_remove_minimum_control(self):
        value = copy.deepcopy(self.policy)
        value["imports"]["catalogs"][0]["exclusions"].append("AM-REVIEW")
        with self.assertRaisesRegex(InputError, "minimum_control_removed"):
            resolve_policy(self.catalog, value)

    def test_unknown_scope_override_and_method_fail_closed(self):
        values = []
        value = copy.deepcopy(self.policy)
        value["scope"]["in"]["technologies"] = ["live-repository"]
        values.append(value)
        value = copy.deepcopy(self.policy)
        value["imports"]["catalogs"][0]["constraints"] = [{"id": "weaken"}]
        values.append(value)
        value = copy.deepcopy(self.policy)
        value["adherence"]["assessment-plans"][0]["evaluation-methods"][0]["id"] = (
            "unknown"
        )
        values.append(value)
        for value in values:
            with self.assertRaises(InputError):
                resolve_policy(self.catalog, value)

    def test_inactive_requirement_is_not_silently_accepted(self):
        value = copy.deepcopy(self.catalog)
        value["controls"][0]["state"] = "Retired"
        with self.assertRaisesRegex(InputError, "inactive_requirement"):
            resolve_policy(value, self.policy)

    def test_digest_is_order_invariant_but_content_sensitive(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))
        self.assertNotEqual(digest({"a": 1}), digest({"a": 2}))


class ArtifactAndRuntimeTests(unittest.TestCase):
    def test_loader_rejects_oversized_and_nonregular_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "oversized.json"
            path.write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(InputError, "input_too_large"):
                load(path)
            with self.assertRaisesRegex(InputError, "regular_file_input_required"):
                load(Path(tmp))
            fifo = Path(tmp) / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(InputError, "regular_file_input_required"):
                load(fifo)

    def test_official_artifact_validation_and_traceability(self):
        package = execute(load(ROOT / "fixtures/satisfied.json"), "baseline")
        report = package["recommendation.json"]
        log = package["evaluation.json"]
        self.assertEqual(log["result"], "Passed")
        self.assertEqual(log["target"]["version"], report["candidate"]["head_sha"])
        for evaluation in log["evaluations"]:
            assessment = evaluation["assessment-logs"][0]
            self.assertEqual(
                assessment["requirement"]["reference-id"],
                evaluation["control"]["reference-id"],
            )
            for evidence in assessment.get("evidence", []):
                self.assertEqual(
                    evidence["source"]["digest"],
                    "sha256:" + digest(evidence["payload"]),
                )
        self.assertTrue(package["comparison.json"]["decisions_match"])
        self.assertFalse(package["run.json"]["llm_used"])

    def test_schema_valid_unsafe_policy_is_rejected_by_resolver(self):
        value = load(ROOT / "policies/baseline.json")
        value["imports"]["catalogs"][0]["exclusions"].append("AM-REVIEW")
        value["adherence"]["assessment-plans"] = [
            p
            for p in value["adherence"]["assessment-plans"]
            if p["requirement-id"] != "AM-REVIEW-1"
        ]
        validate(
            value, "Policy"
        )  # Structural validation is not an authorization decision.
        with self.assertRaisesRegex(InputError, "minimum_control_removed"):
            resolve_policy(load(ROOT / "catalog.json"), value)

    def test_official_schema_rejects_malformed_evaluation(self):
        with self.assertRaises(ValidationError):
            validate({"result": "Passed"}, "EvaluationLog")

    def test_validator_receives_no_inherited_credentials(self):
        import validate as validation

        real_run = validation.subprocess.run
        observed = []

        def capture(*args, **kwargs):
            observed.append(kwargs["env"])
            return real_run(*args, **kwargs)

        with (
            mock.patch.dict(
                os.environ,
                {
                    "GH_TOKEN": "SYNTHETIC_SECRET_SENTINEL",
                    "OPENAI_API_KEY": "SYNTHETIC_SECRET_SENTINEL",
                },
            ),
            mock.patch.object(validation.subprocess, "run", side_effect=capture),
        ):
            package = execute(load(ROOT / "fixtures/satisfied.json"), "baseline")
        self.assertTrue(observed)
        self.assertTrue(all(set(x) == {"PATH", "LANG"} for x in observed))
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(package))

    def test_input_error_does_not_echo_rejected_content_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"secret": "SYNTHETIC_SECRET_SENTINEL"}))
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run.py"),
                    "--evidence",
                    str(path),
                    "--output",
                    str(ROOT / "out" / "rejected-secret-input"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", result.stdout + result.stderr)
            self.assertFalse((ROOT / "out/rejected-secret-input").exists())

    def test_output_cannot_overwrite_controls_or_existing_data(self):
        package = execute(load(ROOT / "fixtures/satisfied.json"), "baseline")
        with self.assertRaisesRegex(InputError, "output_must_be_in_local_out"):
            write_output(package, ROOT / "vendor")
        (ROOT / "out").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp:
            with self.assertRaisesRegex(InputError, "output_exists_or_is_symlink"):
                write_output(package, Path(tmp))


if __name__ == "__main__":
    unittest.main()
