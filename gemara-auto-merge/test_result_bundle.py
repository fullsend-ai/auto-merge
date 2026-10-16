import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import policy_evaluation as p
import result_bundle as b
from test_github_pr_evidence import FixtureClient
from test_policy_evaluation import evidence, NOW
import github_pr_evidence as g


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.bundle = p.load_bundle()
        self.subject = p.subject(repository="fullsend-ai/auto-merge", candidate=True)
        self.result = p.assess(
            self.bundle,
            "candidate",
            self.subject,
            evidence(self.bundle, self.subject, "candidate"),
            NOW,
        )

    def publish(self, directory, result=None):
        with mock.patch.object(b, "new_output", return_value=Path(directory)):
            return b.write_bundle(
                {
                    "repository": "fullsend-ai/auto-merge",
                    "pull_request": 999001,
                    "head_sha": "a" * 40,
                    "base_sha": "b" * 40,
                },
                {"candidate": self.result if result is None else result},
                {"repository": self.bundle},
                "eligible",
                "hold",
                "shadow",
            )

    def test_retains_native_logs_effective_policy_evidence_and_integrity_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            self.publish(d)
            out = Path(d)
            manifest = json.loads((out / "manifest.json").read_text())
            for name, value in manifest["files"].items():
                self.assertEqual(
                    hashlib.sha256((out / name).read_bytes()).hexdigest(), value
                )
            self.assertEqual(
                json.loads((out / "candidate-evaluation-log.json").read_text()),
                self.result["evaluation_log"],
            )
            self.assertTrue(
                json.loads((out / "normalized-evidence.json").read_text())["candidate"]
            )
            summary = (out / "summary.md").read_text()
            self.assertIn("Production readiness: **hold**", summary)
            self.assertIn("carries no merge authority", summary)

    def test_incomplete_or_inconsistent_log_cannot_be_published_as_success(self):
        for kind in ["partial", "empty", "aggregate", "duplicate"]:
            result = copy.deepcopy(self.result)
            if kind == "partial":
                result["evaluation_log"]["evaluations"].pop()
            elif kind == "empty":
                result["assessments"] = []
            elif kind == "aggregate":
                result["evaluation_log"]["result"] = "Failed"
            else:
                result["assessments"].append(result["assessments"][0])
            with tempfile.TemporaryDirectory() as d, self.assertRaises(p.InputError):
                self.publish(d, result)

    def test_real_observer_projection_does_not_export_raw_text_or_credentials(self):
        with mock.patch.dict("os.environ", {"GH_TOKEN": "SYNTHETIC_TOKEN_SENTINEL"}):
            report = g.observe(26, FixtureClient())
            with (
                tempfile.TemporaryDirectory() as d,
                mock.patch.object(b, "new_output", return_value=Path(d)),
            ):
                b.write_bundle(
                    {
                        k: report[k]
                        for k in ["repository", "pull_request", "head_sha", "base_sha"]
                    },
                    {
                        "readiness": report["qualification"]["result"],
                        "candidate": report["shadow"]["evaluation"],
                    },
                    {"repository": self.bundle},
                    "hold",
                    "hold",
                    "shadow",
                )
                text = "".join(x.read_text() for x in Path(d).iterdir())
                self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", text)
                self.assertNotIn("SYNTHETIC_TOKEN_SENTINEL", text)

    def test_failure_bundle_keeps_only_a_stable_code(self):
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.object(b, "new_output", return_value=Path(d)),
        ):
            b.write_failure("raw API text SYNTHETIC_SECRET_SENTINEL", "shadow")
            self.assertNotIn(
                "SYNTHETIC_SECRET_SENTINEL", (Path(d) / "decision.json").read_text()
            )
