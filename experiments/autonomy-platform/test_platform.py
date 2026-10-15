import copy
import json
import os
import subprocess
import unittest
from unittest import mock

import platform_lab as p
from schema import ValidationError

NOW = "2026-10-14T18:00:00Z"


def evidence(bundle, who, purpose):
    values = {"AM-RISK": 1, "AM-CLASS": "documentation"}
    return {
        c["id"]: {
            "subject_sha256": p.digest(who),
            "collected_at": NOW,
            "trusted_source": True,
            "value": values.get(c["id"], True),
        }
        for catalog in bundle["catalogs"].values()
        for c in catalog["controls"]
        if purpose in c["assessment-requirements"][0]["applicability"]
    }


class NativePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = p.load_bundle()

    def setUp(self):
        self.bundle = copy.deepcopy(self.base)
        self.who = p.subject(repository="fullsend-ai/auto-merge", candidate=True)
        self.ready = {
            k: v for k, v in self.who.items() if k not in {"head_sha", "base_sha"}
        }
        self.obs = evidence(self.bundle, self.who, "candidate")
        self.ready_obs = evidence(self.bundle, self.ready, "readiness")

    def evaluate(self, obs=None, bundle=None, who=None):
        return p.assess(
            bundle or self.bundle,
            "candidate",
            who or self.who,
            self.obs if obs is None else obs,
            NOW,
        )

    def test_native_schema_valid_evaluation_traces_catalog_policy_and_plan(self):
        result = self.evaluate()
        self.assertEqual(result["decision"], "eligible")
        self.assertEqual(result["evaluation_log"]["result"], "Passed")
        self.assertEqual(result["sdk_schema_version"], "v1.5.0")
        self.assertEqual(len(result["assessments"]), 7)
        policies = {row["policy"] for row in result["assessments"]}
        self.assertEqual(policies, {"autonomy-common", "autonomy-repository"})
        for control in result["evaluation_log"]["evaluations"]:
            self.assertEqual(control["control"]["reference-id"], "autonomy-controls")
            for assessment in control["assessment-logs"]:
                self.assertIn(assessment["plan"]["reference-id"], policies)
                self.assertTrue(assessment.get("evidence"))

    def test_repository_native_policy_adds_a_requirement_without_replacing_parent(self):
        self.obs["AM-CLASS"]["value"] = "dependency-digest"
        result = self.evaluate()
        rows = {
            x["policy"]: x["state"]
            for x in result["assessments"]
            if x["id"] == "AM-CLASS"
        }
        self.assertEqual(
            rows, {"autonomy-common": "passed", "autonomy-repository": "failed"}
        )
        self.assertEqual(result["decision"], "hold")

    def test_looser_child_plan_cannot_erase_failed_common_assessment(self):
        policy = self.bundle["policies"]["autonomy-repository"]
        parent = self.bundle["policies"]["autonomy-common"]
        risk = copy.deepcopy(
            next(
                x
                for x in parent["adherence"]["assessment-plans"]
                if x["requirement-id"] == "AM-RISK-1"
            )
        )
        risk["id"] = "repository-looser-risk"
        risk["parameters"][0]["accepted-values"] = ["5"]
        policy["adherence"]["assessment-plans"].append(risk)
        self.obs["AM-RISK"]["value"] = 3
        result = self.evaluate()
        self.assertEqual(result["decision"], "hold")
        rows = [x["state"] for x in result["assessments"] if x["id"] == "AM-RISK"]
        self.assertCountEqual(rows, ["failed", "passed"])
        self.assertEqual(result["evaluation_log"]["result"], "Failed")

    def test_missing_stale_future_wrong_subject_and_untrusted_evidence_hold(self):
        for key, value in [
            (None, None),
            ("collected_at", "2026-10-14T17:00:00Z"),
            ("collected_at", "2026-10-14T19:00:00Z"),
            ("subject_sha256", "0" * 64),
            ("trusted_source", False),
        ]:
            obs = copy.deepcopy(self.obs)
            if key is None:
                del obs["AM-REVIEW"]
            else:
                obs["AM-REVIEW"][key] = value
            with self.subTest(key=key, value=value):
                result = self.evaluate(obs)
                self.assertEqual(result["decision"], "hold")
                row = next(x for x in result["assessments"] if x["id"] == "AM-REVIEW")
                self.assertEqual(row["state"], "unknown")

    def test_required_failure_is_not_masked_by_another_pass(self):
        self.obs["AM-CI"]["value"] = False
        self.assertEqual(self.evaluate()["decision"], "hold")

    def test_missing_plan_cannot_turn_into_vacuous_success(self):
        policy = self.bundle["policies"]["autonomy-common"]
        policy["adherence"]["assessment-plans"] = [
            x
            for x in policy["adherence"]["assessment-plans"]
            if x["requirement-id"] != "AM-REVIEW-1"
        ]
        with self.assertRaisesRegex(p.InputError, "missing_assessment_plan"):
            self.evaluate()

    def test_import_version_and_missing_import_fail_closed(self):
        for value in ["wrong-version", "missing-reference"]:
            bundle = copy.deepcopy(self.bundle)
            ref = bundle["policies"]["autonomy-repository"]["metadata"][
                "mapping-references"
            ][0]
            if value == "wrong-version":
                ref["version"] = "99.0.0"
            else:
                bundle["policies"]["autonomy-repository"]["imports"]["policies"][0][
                    "reference-id"
                ] = value
                ref["id"] = value
            with self.subTest(value=value), self.assertRaises(p.InputError):
                self.evaluate(bundle=bundle)

    def test_import_cycle_cannot_recurse_or_execute(self):
        common = self.bundle["policies"]["autonomy-common"]
        common["imports"]["policies"] = [{"reference-id": "autonomy-repository"}]
        common["metadata"]["mapping-references"].append(
            {
                "id": "autonomy-repository",
                "title": "Repository policy",
                "version": "0.1.0",
            }
        )
        with self.assertRaisesRegex(p.InputError, "policy_import_cycle"):
            self.evaluate()

    def test_unknown_method_and_manual_method_do_not_silently_pass(self):
        for key, value in [
            ("id", "execute-arbitrary-script"),
            ("mode", "Manual"),
            ("required", False),
        ]:
            bundle = copy.deepcopy(self.bundle)
            method = bundle["policies"]["autonomy-repository"]["adherence"][
                "assessment-plans"
            ][0]["evaluation-methods"][0]
            method[key] = value
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(p.InputError, "unsupported_evaluation_method"),
            ):
                self.evaluate(bundle=bundle)

    def test_scope_exclusion_and_other_repository_hold(self):
        other = dict(self.who, repository="fullsend-ai/other")
        with self.assertRaisesRegex(p.InputError, "scope_mismatch"):
            self.evaluate(who=other)
        self.bundle["policies"]["autonomy-repository"]["scope"]["out"] = {
            "groups": ["fullsend-ai/auto-merge"]
        }
        with self.assertRaisesRegex(p.InputError, "scope_mismatch"):
            self.evaluate()

    def test_unavailable_scope_dimension_is_not_ignored(self):
        self.bundle["policies"]["autonomy-repository"]["scope"]["in"]["users"] = [
            "maintainers"
        ]
        with self.assertRaisesRegex(p.InputError, "scope_mismatch"):
            self.evaluate()

    def test_unsupported_native_constraint_is_an_explicit_error(self):
        imp = self.bundle["policies"]["autonomy-common"]["imports"]["catalogs"][0]
        imp["constraints"] = [
            {
                "id": "constraint-1",
                "target-id": "AM-CI",
                "text": "Manual requirement needs a supported evaluator",
            }
        ]
        with self.assertRaisesRegex(p.InputError, "unsupported_catalog_modification"):
            self.evaluate()

    def test_risk_acceptance_does_not_silently_waive_controls(self):
        policy = self.bundle["policies"]["autonomy-repository"]
        policy["risks"] = {
            "accepted": [
                {
                    "id": "acceptance-1",
                    "risk": {
                        "reference-id": "autonomy-controls",
                        "entry-id": "AM-RISK",
                    },
                    "justification": "Requires a supported risk evaluator and approval contract",
                }
            ]
        }
        with self.assertRaisesRegex(p.InputError, "unsupported_policy_semantics"):
            self.evaluate()

    def test_policy_freshness_parameter_cannot_extend_runtime_cap(self):
        plan = self.bundle["policies"]["autonomy-repository"]["adherence"][
            "assessment-plans"
        ][0]
        plan["parameters"].append(
            {
                "id": "maximum-age-seconds",
                "label": "Evidence age",
                "description": "Native method parameter",
                "accepted-values": ["601"],
            }
        )
        with self.assertRaisesRegex(p.InputError, "invalid_freshness"):
            self.evaluate()

    def test_schema_rejects_unknown_native_fields_before_execution(self):
        self.bundle["policies"]["autonomy-repository"]["private_instruction"] = (
            "SYNTHETIC_SENTINEL"
        )
        real = p.subprocess.run
        native_calls = []

        def observe(*args, **kwargs):
            if str(args[0][0]).endswith("gemara-evaluator"):
                native_calls.append(args)
            return real(*args, **kwargs)

        with (
            mock.patch("platform_lab.subprocess.run", side_effect=observe),
            self.assertRaises(ValidationError) as error,
        ):
            self.evaluate()
        self.assertNotIn("SYNTHETIC_SENTINEL", str(error.exception))
        self.assertEqual(native_calls, [])

    def test_four_modes_never_authorize_mutation(self):
        receipt = p.qualification(self.bundle, self.ready, NOW, self.ready_obs)
        for mode in p.MODES:
            result = p.gate(self.bundle, self.who, NOW, self.obs, mode, receipt)
            self.assertFalse(result["mutation_permitted"])
            self.assertEqual(result["authorized_actions"], [])
            self.assertEqual(
                result["decision"],
                "would_allow" if mode in {"shadow", "gemara"} else "hold",
            )

    def test_candidate_pass_does_not_override_missing_readiness(self):
        receipt = p.qualification(self.bundle, self.ready, NOW, {})
        for mode in ["shadow", "light", "gemara"]:
            result = p.gate(self.bundle, self.who, NOW, self.obs, mode, receipt)
            self.assertEqual(result["evaluation"]["decision"], "eligible")
            self.assertEqual(result["decision"], "hold")
            self.assertIn("qualification_unavailable", result["reasons"])
            self.assertFalse(result["mutation_permitted"])

    def test_off_does_not_execute_evaluator(self):
        with mock.patch(
            "platform_lab.assess", side_effect=AssertionError("off must not execute")
        ):
            self.assertEqual(
                p.gate(self.bundle, self.who, NOW, {}, "off", None)["decision"], "hold"
            )

    def test_qualification_binds_configuration_policy_and_expiry(self):
        receipt = p.qualification(self.bundle, self.ready, NOW, self.ready_obs)
        who = dict(self.who, configuration_sha256="d" * 64)
        self.assertIn(
            "qualification_unavailable",
            p.gate(self.bundle, who, NOW, self.obs, "shadow", receipt)["reasons"],
        )
        later = "2026-10-14T18:11:00Z"
        self.assertIn(
            "qualification_expired",
            p.gate(self.bundle, self.who, later, self.obs, "shadow", receipt)[
                "reasons"
            ],
        )
        self.bundle["policies"]["autonomy-repository"]["metadata"]["description"] += (
            " Revised"
        )
        self.assertIn(
            "qualification_unavailable",
            p.gate(self.bundle, self.who, NOW, self.obs, "shadow", receipt)["reasons"],
        )

    def test_evaluator_child_does_not_inherit_credentials(self):
        real = p.subprocess.run
        seen = []

        def observe(*args, **kwargs):
            if str(args[0][0]).endswith("gemara-evaluator"):
                seen.append(kwargs["env"])
            return real(*args, **kwargs)

        with (
            mock.patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC_SENTINEL"}),
            mock.patch("platform_lab.subprocess.run", side_effect=observe),
        ):
            result = self.evaluate()
        self.assertEqual(set(seen[0]), {"PATH", "LANG"})
        self.assertNotIn("SYNTHETIC_SENTINEL", json.dumps(result))

    def test_duplicate_json_does_not_echo_or_execute_supplied_data(self):
        child = subprocess.run(
            [str(p.ROOT / ".tools/gemara-evaluator")],
            input='{"root_policy":"SYNTHETIC_SENTINEL","root_policy":"duplicate"}',
            text=True,
            capture_output=True,
            timeout=5,
            env={"PATH": "/usr/bin:/bin"},
        )
        self.assertNotEqual(child.returncode, 0)
        self.assertNotIn("SYNTHETIC_SENTINEL", child.stdout + child.stderr)
        self.assertFalse(json.loads(child.stdout)["mutation_permitted"])


if __name__ == "__main__":
    unittest.main()
