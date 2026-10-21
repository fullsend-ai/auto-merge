import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayCollectionTests(unittest.TestCase):
    def setUp(self):
        self.collector = load_script("collect_review_replay")
        self.binding = json.loads(
            (ROOT / ".fullsend/shared-review-replay.json").read_text()
        )
        b = self.binding
        s = b["source"]
        publisher = b"synthetic publisher"
        s["publisher_sha256"] = hashlib.sha256(publisher).hexdigest()
        self.run = {
            "id": s["run_id"],
            "run_attempt": 1,
            "repository": {"id": b["project_id"]},
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request_target",
            "path": ".github/workflows/fullsend.yaml",
            "head_sha": b["head_sha"],
            "referenced_workflows": [
                {
                    "sha": s["fullsend_commit"],
                    "path": "fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@"
                    + s["fullsend_commit"],
                }
            ],
        }
        self.publisher = {"content": base64.b64encode(publisher).decode()}
        self.artifact = {
            "expired": False,
            "workflow_run": {"id": s["run_id"], "head_sha": b["head_sha"]},
            "name": "fullsend-review-evidence-1",
            "size_in_bytes": 100,
            "digest": "sha256:" + "a" * 64,
        }
        self.record = {
            "review": {
                "action": "approve",
                "risk": {"score": 1, "level": "low"},
                "findings": [],
            }
        }

    def collect(self):
        replies = [
            json.dumps(v).encode() for v in [self.run, self.publisher, self.artifact]
        ]
        with (
            mock.patch.object(self.collector, "get", side_effect=replies),
            mock.patch(
                "native_review_artifacts.download", return_value=b"synthetic archive"
            ),
            mock.patch(
                "review_evidence_retention.extract_record",
                return_value=json.dumps(self.record).encode(),
            ) as extract,
        ):
            result = self.collector.github(self.binding)
            extract.assert_called_once()
            subject = extract.call_args.args[2]
            self.assertEqual(
                subject["configuration_sha"],
                self.binding["source"]["configuration_sha"],
            )
            return result

    def test_success_binds_reviewed_head_and_retained_configuration_separately(self):
        self.assertNotEqual(
            self.run["head_sha"], self.binding["source"]["configuration_sha"]
        )
        result, ledger, digest = self.collect()
        self.assertEqual(result["head_sha"], self.binding["head_sha"])
        self.assertEqual(ledger["findings"], [])
        self.assertEqual(digest, self.artifact["digest"])

    def test_run_identity_and_source_pin_rejections(self):
        for field, bad, reason in [
            ("conclusion", "failure", "untrusted_review_run"),
            ("event", "pull_request", "untrusted_review_run"),
            ("run_attempt", 2, "wrong_review_run"),
            ("head_sha", "b" * 40, "wrong_review_run_head"),
            ("referenced_workflows", [], "wrong_review_harness"),
        ]:
            original = copy.deepcopy(self.run)
            self.run[field] = bad
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason):
                self.collect()
            self.run = original
        self.publisher["content"] = base64.b64encode(b"changed publisher").decode()
        with self.assertRaisesRegex(ValueError, "publisher_pin_mismatch"):
            self.collect()
        self.binding["source"]["configuration_sha"] = "bad?ref=other"
        with self.assertRaisesRegex(ValueError, "invalid_source_sha"):
            self.collect()

    def test_artifact_rejections(self):
        for field, bad, reason in [
            ("expired", True, "replay_source_expired"),
            ("name", "wrong", "wrong_review_artifact"),
            ("workflow_run", {"id": 1, "head_sha": "b" * 40}, "wrong_review_artifact"),
            ("size_in_bytes", 0, "artifact_too_large"),
            ("size_in_bytes", 300000, "artifact_too_large"),
        ]:
            original = copy.deepcopy(self.artifact)
            self.artifact[field] = bad
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason):
                self.collect()
            self.artifact = original


class SharedLauncherTests(unittest.TestCase):
    def launch(self, change=None, exit_code=0, bad_checksum=False):
        launcher = load_script("run_shared_review")
        pin = ROOT / ".fullsend/shared-review-tool.json"
        expected = json.loads(pin.read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            inputs.mkdir()
            context = dict(
                mode="retained-review-replay",
                authorization="none",
                head_sha="a" * 40,
                maximum_risk=2,
            )
            (inputs / "context.json").write_text(json.dumps(context))
            for name in ["result.json", "ledger.json"]:
                (inputs / name).write_text("{}")

            def command(args, **kwargs):
                env = kwargs["env"]
                self.assertNotIn("GH_TOKEN", env)
                self.assertNotIn("CI_JOB_TOKEN", env)
                output = kwargs["output"]
                if args[1:3] == ["mod", "download"]:
                    value = dict(
                        Sum="changed" if bad_checksum else expected["source_sum"],
                        Version=expected["version"],
                        Origin={"Hash": expected["commit"]},
                    )
                elif args[1] == "install":
                    binary = Path(env["GOBIN"]) / "gemara-owner"
                    binary.parent.mkdir(parents=True)
                    binary.write_bytes(b"synthetic")
                    value = {}
                elif args[1] == "project-review":
                    value = dict(
                        schema_version="review-projection/v1",
                        head_sha=context["head_sha"],
                        authorization="none",
                        mutation_permitted=False,
                    )
                    if change:
                        change("projection", value)
                elif args[1] == "check-review":
                    value = dict(
                        schema_version="review-check/v1",
                        head_sha=context["head_sha"],
                        authorization="none",
                        mutation_permitted=False,
                        decision="eligible",
                        reason="review_requirements_satisfied",
                    )
                    if change:
                        change("assessment", value)
                    output.write_text(json.dumps(value))
                    return exit_code
                output.write_text(json.dumps(value))
                return 0

            with (
                mock.patch(
                    "sys.argv",
                    [
                        "runner",
                        "--input",
                        str(inputs),
                        "--pin",
                        str(pin),
                        "--output",
                        str(root / "report"),
                    ],
                ),
                mock.patch.object(launcher.shutil, "which", return_value="/trusted/go"),
                mock.patch.object(launcher, "run", side_effect=command),
            ):
                return launcher.main()

    def test_success_and_checksum_rejection(self):
        self.assertEqual(self.launch(), 0)
        with self.assertRaisesRegex(ValueError, "shared_source_checksum_mismatch"):
            self.launch(bad_checksum=True)

    def test_privilege_or_wrong_revision_rejected_in_projection_and_assessment(self):
        for phase in ["projection", "assessment"]:
            for field, bad in [
                ("mutation_permitted", True),
                ("authorization", "merge"),
                ("head_sha", "b" * 40),
            ]:

                def alter(actual, value):
                    if actual == phase:
                        value[field] = bad

                with (
                    self.subTest(phase=phase, field=field),
                    self.assertRaisesRegex(ValueError, "invalid_shared_" + phase),
                ):
                    self.launch(change=alter)

    def test_exit_conflicts_and_log_commands_rejected(self):
        def hold(phase, value):
            if phase == "assessment":
                value["decision"] = "hold"

        with self.assertRaisesRegex(ValueError, "assessment_exit_conflict"):
            self.launch(change=hold, exit_code=0)
        with self.assertRaisesRegex(ValueError, "assessment_exit_conflict"):
            self.launch(exit_code=2)

        def malicious_reason(phase, value):
            if phase == "assessment":
                value["reason"] = "ok\n::error::forged"

        with self.assertRaisesRegex(ValueError, "invalid_assessment_reason"):
            self.launch(change=malicious_reason)
        self.assertEqual(self.launch(change=hold, exit_code=2), 2)

    def test_privileged_publisher_unchanged(self):
        raw = (ROOT / ".fullsend/scripts/publish-review-evidence.py").read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "57512e9b5ea0506aaaaa489d33929858beeedd836460c10e0a1dbf9e21f35f2e",
        )
        self.assertIn(b'"degraded" not in risk', raw)


if __name__ == "__main__":
    unittest.main()
