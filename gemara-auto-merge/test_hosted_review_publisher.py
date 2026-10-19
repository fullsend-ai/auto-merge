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

from policy_evaluation import InputError
from review_evidence_contract import PublicationProof, consume, encode_post_script


class PublisherTests(unittest.TestCase):
    def publish(
        self,
        *,
        changed_pr=False,
        invalid_risk=False,
        wrong_digest=False,
        destination_symlink=False,
        oversized=False,
    ):
        path = (
            Path(__file__).resolve().parents[1]
            / ".fullsend/scripts/publish-review-evidence.py"
        )
        spec = importlib.util.spec_from_file_location("postscript_publisher", path)
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".fullsend").mkdir()
            producer = {
                "schema_version": "review-post-script-producer/v1",
                "source_commit": "c" * 40,
                "publisher_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            if wrong_digest:
                producer["publisher_sha256"] = "f" * 64
            (workspace / ".fullsend/review-evidence-producer.json").write_text(
                json.dumps(producer)
            )
            result = workspace / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "head_sha": "a" * 40,
                        "body": "SYNTHETIC_PRIVATE_PROSE",
                        "risk_assessment": {
                            "score": 6 if invalid_risk else 1,
                            "level": "low",
                            "explanation": "SYNTHETIC_PRIVATE_PROSE",
                        },
                    }
                )
            )
            pr = {
                "head": {"sha": "f" * 40 if changed_pr else "a" * 40},
                "base": {
                    "sha": "b" * 40,
                    "repo": {"full_name": "fullsend-ai/auto-merge"},
                },
            }
            projection = {"version": 2, "action": "approve", "findings": []}
            if oversized:
                projection["padding"] = "x" * (128 * 1024)
            destination = workspace / "output/fullsend-review-evidence.json"
            if destination_symlink:
                destination.parent.mkdir()
                destination.symlink_to(result)
            opener = mock.MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(pr).encode()
            )
            env = {
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_REPOSITORY": "fullsend-ai/auto-merge",
                "GITHUB_REPOSITORY_ID": "1383516376",
                "PR_URL": "https://github.com/fullsend-ai/auto-merge/pull/999001",
                "GITHUB_RUN_ID": "1234",
                "GITHUB_RUN_ATTEMPT": "1",
                "REVIEW_TOKEN": "SYNTHETIC_TOKEN",
            }
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch("sys.argv", ["publisher", str(result)]),
                mock.patch("sys.stdin", io.StringIO(json.dumps(projection))),
                mock.patch.object(
                    host.urllib.request, "build_opener", return_value=opener
                ),
                mock.patch.object(
                    host.subprocess, "check_output", return_value="b" * 40
                ),
                mock.patch.object(host.subprocess, "run") as command,
                mock.patch.object(host, "project_review", return_value={
                    "completed": True, "action": "approve", "findings": [],
                    "risk_score": 6 if invalid_risk else 1,
                }),
                mock.patch("builtins.print"),
            ):
                try:
                    host.main()
                except Exception:
                    if not destination_symlink:
                        self.assertFalse(destination.exists())
                    raise
            command.assert_not_called()
            record = json.loads(destination.read_text())
            self.assertNotIn("SYNTHETIC_PRIVATE_PROSE", destination.read_text())
            self.assertNotIn("SYNTHETIC_TOKEN", destination.read_text())
            self.assertFalse((workspace / ".fullsend/bin/fullsend").exists())
            return record

    def test_shared_helper_has_no_forge_credentials_and_rejects_failure(self):
        path = Path(__file__).resolve().parents[1] / ".fullsend/scripts/publish-review-evidence.py"
        spec = importlib.util.spec_from_file_location("shared_publisher", path)
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        value = {"schema_version": "review-projection/v1", "head_sha": "a" * 40,
                 "authorization": "none", "mutation_permitted": False,
                 "review": {"completed": True, "action": "approve", "risk_score": 1, "findings": []}}
        result = mock.Mock(returncode=0, stdout=json.dumps(value))
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            with mock.patch.dict(os.environ, {"REVIEW_TOKEN": "SYNTHETIC_TOKEN", "GITHUB_TOKEN": "SYNTHETIC_TOKEN"}), mock.patch.object(host.shutil, "which", return_value="/trusted/go"), mock.patch.object(host.subprocess, "run", return_value=result) as command:
                self.assertEqual(host.project_review(result_path, "{}", "a" * 40), value["review"])
                kwargs = command.call_args.kwargs
                self.assertNotIn("REVIEW_TOKEN", kwargs["env"])
                self.assertNotIn("GITHUB_TOKEN", kwargs["env"])
                self.assertNotIn("SYNTHETIC_TOKEN", json.dumps(kwargs))
                self.assertIn("@a73a3d88471f1fe5e947b11936430d7b298091f2", command.call_args.args[0][2])
                self.assertFalse(kwargs.get("shell", False))
                result.returncode = 1
                with self.assertRaisesRegex(ValueError, "shared_review_projection_failed"):
                    host.project_review(result_path, "{}", "a" * 40)
                result.returncode = 0
                value["head_sha"] = "b" * 40
                result.stdout = json.dumps(value)
                with self.assertRaisesRegex(ValueError, "invalid_shared_projection"):
                    host.project_review(result_path, "{}", "a" * 40)

    def test_postscript_publishes_consumable_evidence_without_a_binary(self):
        record = self.publish()
        self.assertEqual(record["schema_version"], "fullsend-review-evidence/v2")
        self.assertEqual(record["producer"]["kind"], "fullsend-post-script-lab")
        proof = PublicationProof(
            record["subject"],
            record["producer"],
            record["payload_sha256"],
            "completed",
            "success",
            True,
        )
        result = consume(record, record["subject"], proof, record["issued_at"])
        self.assertEqual(result["reason"], "contract_verified")
        self.assertEqual(result["values"]["AM-RISK"], 1)
        self.assertFalse(result["merge_authority"])

    def test_changed_head_invalid_risk_or_source_and_unsafe_destination_fail_closed(
        self,
    ):
        for option in [
            "changed_pr",
            "invalid_risk",
            "wrong_digest",
            "destination_symlink",
            "oversized",
        ]:
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.publish(**{option: True})

    def test_versioned_encoder_preserves_adverse_findings_and_refuses_reserved_metadata(
        self,
    ):
        record = self.publish()
        value = {
            k: v
            for k, v in record.items()
            if k not in {"schema_version", "payload_sha256"}
        }
        value["review"]["findings"] = [
            {
                "id": "f_one",
                "severity": "low",
                "category": "missing-doc",
                "status": "open",
            }
        ]
        encoded = json.loads(encode_post_script(value))
        proof = PublicationProof(
            encoded["subject"],
            encoded["producer"],
            encoded["payload_sha256"],
            "completed",
            "success",
            True,
        )
        result = consume(encoded, encoded["subject"], proof, encoded["issued_at"])
        self.assertTrue(result["values"]["AM-REVIEW"])
        self.assertFalse(result["values"]["AM-FINDINGS"])
        for key in ["schema_version", "payload_sha256"]:
            with self.assertRaises(InputError):
                encode_post_script(dict(value, **{key: "injected"}))
        tampered = copy.deepcopy(encoded)
        tampered["producer"]["publisher_sha256"] = "f" * 64
        self.assertEqual(
            consume(tampered, encoded["subject"], proof, encoded["issued_at"])[
                "reason"
            ],
            "contract_integrity_mismatch",
        )
