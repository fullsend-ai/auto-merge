import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayCollectionTests(unittest.TestCase):
    def gitlab_case(self, *, changed_head=False, wrong_author=False, duplicate=False, protected=False):
        collector = load_script("collect_review_replay")
        head = "a" * 40
        binding = {"host": "gitlab.example.test", "project_id": 123, "repository": "example/consumer", "change": 6, "head_sha": head, "source": {"note_id": 2, "job_id": 3, "review_author": "project_123_bot_synthetic", "result_member": "output/result.json"}}
        ledger = {"version": 2, "action": "approve", "findings": []}
        marker = "<!-- fullsend:review-findings-v2:" + base64.b64encode(json.dumps(ledger).encode()).decode() + " -->"
        note = {"author": {"username": "wrong" if wrong_author else binding["source"]["review_author"]}, "system": False, "body": "<!-- fullsend:review-agent -->\n<!-- **Head SHA:** " + head + " -->\n" + marker + ("\n" + marker if duplicate else "")}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("output/result.json", json.dumps({"head_sha": head, "action": "approve", "risk_assessment": None, "body": "SYNTHETIC_PRIVATE_PROSE"}))
        responses = [json.dumps({"iid": 6, "project_id": 123, "sha": "b" * 40 if changed_head else head}).encode(), json.dumps(note).encode(), output.getvalue()]
        env = {"CI_COMMIT_REF_PROTECTED": "true" if protected else "false", "CI_PROJECT_ID": "123", "CI_PROJECT_PATH": "example/consumer", "CI_SERVER_HOST": "gitlab.example.test", "CI_JOB_TOKEN": "SYNTHETIC_TOKEN"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(collector, "get", side_effect=responses):
            return collector.gitlab(binding)

    def test_gitlab_authenticates_note_and_drops_prose_without_inventing_risk(self):
        result, ledger, digest = self.gitlab_case()
        self.assertIsNone(result["risk_assessment"])
        self.assertEqual(ledger["findings"], [])
        self.assertNotIn("SYNTHETIC_PRIVATE_PROSE", json.dumps(result))
        self.assertTrue(digest.startswith("sha256:"))

    def test_gitlab_changed_head_author_ambiguous_ledger_and_protected_job_hold(self):
        for option in ["changed_head", "wrong_author", "duplicate", "protected"]:
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.gitlab_case(**{option: True})

    def test_github_rejects_untrusted_run_and_changed_publisher(self):
        collector = load_script("collect_review_replay")
        binding = json.loads((ROOT / ".fullsend/shared-review-replay.json").read_text())
        source = b"synthetic publisher source"
        binding["source"]["publisher_sha256"] = hashlib.sha256(source).hexdigest()
        run = {"id": binding["source"]["run_id"], "run_attempt": 1, "repository": {"id": binding["project_id"]}, "status": "completed", "conclusion": "success", "event": "pull_request_target", "path": ".github/workflows/fullsend.yaml"}
        for field, bad in [("conclusion", "failure"), ("event", "pull_request"), ("run_attempt", 2)]:
            altered = copy.deepcopy(run)
            altered[field] = bad
            with self.subTest(field=field), mock.patch.object(collector, "get", return_value=json.dumps(altered).encode()), self.assertRaises(ValueError):
                collector.github(binding)
        responses = [json.dumps(run).encode(), json.dumps({"content": base64.b64encode(b"changed publisher").decode()}).encode()]
        with mock.patch.object(collector, "get", side_effect=responses), self.assertRaisesRegex(ValueError, "publisher_pin_mismatch"):
            collector.github(binding)


class SharedLauncherTests(unittest.TestCase):
    def test_changed_source_checksum_stops_before_build_or_execution(self):
        launcher = load_script("run_shared_review")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            inputs.mkdir()
            (inputs / "context.json").write_text(json.dumps({"mode": "retained-review-replay", "authorization": "none", "head_sha": "a" * 40, "maximum_risk": 2}))
            pin = ROOT / ".fullsend/shared-review-tool.json"
            expected = json.loads(pin.read_text())
            def downloaded(args, **kwargs):
                self.assertNotIn("GH_TOKEN", kwargs["env"])
                self.assertNotIn("CI_JOB_TOKEN", kwargs["env"])
                self.assertEqual(kwargs["env"]["CGO_ENABLED"], "0")
                kwargs["output"].write_text(json.dumps({"Sum": "changed", "Version": expected["version"], "Origin": {"Hash": expected["commit"]}}))
            with (
                mock.patch("sys.argv", ["runner", "--input", str(inputs), "--pin", str(pin), "--output", str(root / "report")]),
                mock.patch.object(launcher.shutil, "which", return_value="/trusted/go"),
                mock.patch.object(launcher, "run", side_effect=downloaded) as command,
                self.assertRaisesRegex(ValueError, "shared_source_checksum_mismatch"),
            ):
                launcher.main()
            self.assertEqual(command.call_count, 1)

    def test_privileged_publisher_does_not_execute_shared_code(self):
        original = (ROOT / ".fullsend/scripts/publish-review-evidence.py").read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), "57512e9b5ea0506aaaaa489d33929858beeedd836460c10e0a1dbf9e21f35f2e")
        self.assertIn(b'"degraded" not in risk', original)


if __name__ == "__main__":
    unittest.main()
