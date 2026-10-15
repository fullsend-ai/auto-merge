import copy
import json
import os
import tempfile
import unittest
from unittest import mock

from platform_lab import (
    ROOT,
    InputError,
    assess,
    digest,
    gate,
    load,
    observations_for,
    qualification,
    request,
    resolve,
    subject,
)

NOW = "2026-10-14T18:00:00Z"
ADAPTERS = ["gemara-sdk", "native-json-reference"]


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.shared = load(ROOT / "policies/shared.json")
        self.repo = load(ROOT / "policies/repository.json")
        self.policy = resolve(self.shared, self.repo)
        self.ready = subject()
        self.who = subject(candidate=True)
        self.ready_obs = observations_for(self.ready, self.policy["readiness"], NOW)
        self.obs = observations_for(self.who, self.policy["candidate"], NOW)

    def req(self, observations=None):
        return request(
            self.policy,
            "candidate",
            self.who,
            self.obs if observations is None else observations,
            NOW,
        )

    def both(self, req):
        values = [assess(req, a) for a in ADAPTERS]
        self.assertEqual(values[0]["decision"], values[1]["decision"])
        self.assertEqual(values[0]["assessments"], values[1]["assessments"])
        return values

    def test_independent_adapters_match_all_rule_outcomes(self):
        for rule in self.policy["candidate"]:
            for value in [True, False, None, 0, 3, "documentation", "unapproved"]:
                obs = copy.deepcopy(self.obs)
                obs[rule["id"]]["value"] = value
                with self.subTest(control=rule["id"], value=value):
                    self.both(self.req(obs))

    def test_four_modes_never_mutate(self):
        for adapter in ADAPTERS:
            receipt = qualification(
                self.policy, self.ready, NOW, self.ready_obs, adapter
            )
            for mode in ["off", "shadow", "light", "policy"]:
                result = gate(
                    self.policy, self.who, NOW, self.obs, mode, receipt, adapter
                )
                self.assertEqual(
                    result["decision"], "hold" if mode == "off" else "would_allow"
                )
                self.assertFalse(result["mutation_permitted"])
                self.assertEqual(result["authorized_actions"], [])

    def test_light_scope_differs_from_governed_policy(self):
        self.obs["AM-CLASS"]["value"] = "documentation"
        for adapter in ADAPTERS:
            receipt = qualification(
                self.policy, self.ready, NOW, self.ready_obs, adapter
            )
            self.assertIn(
                "outside_light_class",
                gate(self.policy, self.who, NOW, self.obs, "light", receipt, adapter)[
                    "reasons"
                ],
            )
            self.assertEqual(
                gate(self.policy, self.who, NOW, self.obs, "policy", receipt, adapter)[
                    "decision"
                ],
                "would_allow",
            )

    def test_each_readiness_control_can_prevent_qualification(self):
        for rule in self.policy["readiness"]:
            obs = copy.deepcopy(self.ready_obs)
            obs[rule["id"]]["value"] = False
            for adapter in ADAPTERS:
                r = qualification(self.policy, self.ready, NOW, obs, adapter)
                self.assertEqual(r["decision"], "hold")
                self.assertIn(
                    "qualification_unavailable",
                    gate(self.policy, self.who, NOW, self.obs, "shadow", r, adapter)[
                        "reasons"
                    ],
                )

    def test_configuration_policy_and_time_revoke_qualification(self):
        for adapter in ADAPTERS:
            receipt = qualification(
                self.policy, self.ready, NOW, self.ready_obs, adapter
            )
            changed = copy.deepcopy(self.who)
            changed["configuration_sha256"] = "d" * 64
            self.assertIn(
                "qualification_unavailable",
                gate(self.policy, changed, NOW, self.obs, "shadow", receipt, adapter)[
                    "reasons"
                ],
            )
            newer_repo = copy.deepcopy(self.repo)
            newer_repo["maximum_risk"] = 0
            newer = resolve(self.shared, newer_repo)
            self.assertIn(
                "qualification_unavailable",
                gate(newer, self.who, NOW, self.obs, "shadow", receipt, adapter)[
                    "reasons"
                ],
            )
            self.assertIn(
                "qualification_expired",
                gate(
                    self.policy,
                    self.who,
                    "2026-10-14T18:10:01Z",
                    self.obs,
                    "shadow",
                    receipt,
                    adapter,
                )["reasons"],
            )

    def test_revision_or_base_or_repository_cannot_reuse_evidence(self):
        for key, value in [
            ("head_sha", "d" * 40),
            ("base_sha", "e" * 40),
            ("repository", "example/other"),
        ]:
            changed = copy.deepcopy(self.who)
            changed[key] = value
            req = request(self.policy, "candidate", changed, self.obs, NOW)
            self.assertEqual(self.both(req)[0]["decision"], "hold")

    def test_missing_stale_future_wrong_subject_and_untrusted(self):
        variants = []
        obs = copy.deepcopy(self.obs)
        del obs["AM-REVIEW"]
        variants.append(obs)
        for key, value in [
            ("collected_at", "2026-10-14T17:49:59Z"),
            ("collected_at", "2026-10-14T18:00:01Z"),
            ("trusted_source", False),
            ("subject_sha256", "f" * 64),
        ]:
            obs = copy.deepcopy(self.obs)
            obs["AM-REVIEW"][key] = value
            variants.append(obs)
        for obs in variants:
            self.assertEqual(self.both(self.req(obs))[0]["decision"], "hold")

    def test_repo_adds_requirement_and_tightens_risk(self):
        self.repo["additional_checks"] = [
            {"id": "AM-SECURITY", "kind": "boolean", "expected": True}
        ]
        self.policy = resolve(self.shared, self.repo)
        self.assertEqual(self.both(self.req())[0]["decision"], "hold")
        self.obs["AM-SECURITY"] = {
            "subject_sha256": digest(self.who),
            "collected_at": NOW,
            "trusted_source": True,
            "value": True,
        }
        self.assertEqual(self.both(self.req())[0]["decision"], "eligible")
        self.obs["AM-RISK"]["value"] = 2
        self.assertEqual(self.both(self.req())[0]["decision"], "hold")

    def test_policy_weakening_and_unknown_instructions_rejected(self):
        for key, value in [
            ("maximum_risk", 3),
            ("classes", ["arbitrary"]),
            ("exclusions", ["AM-REVIEW"]),
            ("command", "anything"),
        ]:
            repo = copy.deepcopy(self.repo)
            repo[key] = value
            with self.assertRaises(InputError):
                resolve(self.shared, repo)
        with self.assertRaisesRegex(InputError, "untrusted_policy"):
            resolve(self.shared, self.repo, trusted=False)
        for purpose in ["readiness", "candidate"]:
            shared = copy.deepcopy(self.shared)
            shared[purpose].pop()
            with self.assertRaisesRegex(InputError, "minimum_removed"):
                resolve(shared, self.repo)

    def test_candidate_cannot_change_trusted_policy_and_protected_paths_hold(self):
        self.obs["AM-PROTECTED"]["value"] = False
        self.assertEqual(self.both(self.req())[0]["decision"], "hold")

    def test_bad_requests_do_not_succeed(self):
        for key, value in [
            ("rules", []),
            ("maximum_age_seconds", 601),
            ("subject_sha256", "not-a-digest"),
        ]:
            req = self.req()
            req[key] = value
            for adapter in ADAPTERS:
                with self.assertRaises(InputError):
                    assess(req, adapter)
        req = self.req()
        req["observations"]["AM-REVIEW"]["value"] = {"secret": "SYNTHETIC_SENTINEL"}
        with self.assertRaises(InputError):
            assess(req, "gemara-sdk")

    def test_sdk_captures_evidence_for_pass_fail_and_unknown(self):
        for key, replacement in [(None, None), ("AM-CI", False), ("AM-REVIEW", None)]:
            obs = copy.deepcopy(self.obs)
            if key:
                if replacement is None:
                    del obs[key]
                else:
                    obs[key]["value"] = replacement
            req = self.req(obs)
            result = assess(req, "gemara-sdk")
            evidence = [
                e
                for c in result["sdk_evaluations"]
                for a in c["assessment-logs"]
                for e in a.get("evidence", [])
            ]
            self.assertTrue(evidence)
            self.assertEqual(result["sdk_schema_version"], "v1.5.0")
            self.assertEqual(evidence[0]["source"]["reference-id"], "observations")

    def test_sdk_child_has_clean_environment(self):
        import platform_lab

        real = platform_lab.subprocess.run
        seen = []

        def observe(*a, **kw):
            seen.append(kw["env"])
            return real(*a, **kw)

        with (
            mock.patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC_SENTINEL"}),
            mock.patch.object(platform_lab.subprocess, "run", side_effect=observe),
        ):
            result = assess(self.req(), "gemara-sdk")
        self.assertEqual(set(seen[0]), {"PATH", "LANG"})
        self.assertNotIn("SYNTHETIC_SENTINEL", json.dumps(result))

    def test_alternative_adapter_needs_no_sdk_or_cue_process(self):
        with mock.patch(
            "platform_lab.subprocess.run",
            side_effect=AssertionError("unexpected external process"),
        ):
            self.assertEqual(
                assess(self.req(), "native-json-reference")["decision"], "eligible"
            )

    def test_switching_engine_requires_new_qualification(self):
        receipt = qualification(
            self.policy, self.ready, NOW, self.ready_obs, "gemara-sdk"
        )
        self.assertIn(
            "qualification_unavailable",
            gate(
                self.policy,
                self.who,
                NOW,
                self.obs,
                "shadow",
                receipt,
                "native-json-reference",
            )["reasons"],
        )

    def test_extra_equality_rule_has_consistent_typed_behavior(self):
        self.repo["additional_checks"] = [
            {"id": "AM-SCANNER", "kind": "equals", "expected": "success"}
        ]
        self.policy = resolve(self.shared, self.repo)
        for value in [True, False, 0, None, "success", "failure"]:
            self.obs["AM-SCANNER"] = {
                "subject_sha256": digest(self.who),
                "collected_at": NOW,
                "trusted_source": True,
                "value": value,
            }
            self.both(self.req())

    def test_output_symlink_is_rejected(self):
        import platform_lab
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "outside").mkdir()
            (root / "out").symlink_to(root / "outside", target_is_directory=True)
            with mock.patch.object(platform_lab, "ROOT", root):
                with self.assertRaisesRegex(InputError, "symlink_output"):
                    platform_lab.new_output("test")


if __name__ == "__main__":
    unittest.main()
