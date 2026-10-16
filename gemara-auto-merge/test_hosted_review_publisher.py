import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_review_evidence_contract import fixture


class PublisherTests(unittest.TestCase):
    def test_host_metadata_and_allowlisted_projection_not_model_prose_are_published(
        self,
    ):
        path = (
            Path(__file__).resolve().parents[1]
            / ".fullsend/scripts/publish-review-evidence.py"
        )
        spec = importlib.util.spec_from_file_location("native_publisher", path)
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            binary = workspace / ".fullsend/bin/fullsend"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"SYNTHETIC_BINARY")
            build = {
                "source_commit": "c" * 40,
                "overlay_sha256": "d" * 64,
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            }
            (workspace / ".fullsend/evidence-build.json").write_text(json.dumps(build))
            result = workspace / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "head_sha": "a" * 40,
                        "body": "SYNTHETIC_PRIVATE_PROSE",
                        "risk_assessment": {
                            "score": 1,
                            "level": "low",
                            "explanation": "SYNTHETIC_PRIVATE_PROSE",
                        },
                    }
                )
            )
            pr = {
                "head": {"sha": "a" * 40},
                "base": {
                    "sha": "b" * 40,
                    "repo": {"full_name": "fullsend-ai/auto-merge"},
                },
            }
            projection = {"version": 2, "action": "approve", "findings": []}
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
                mock.patch.dict(os.environ, env),
                mock.patch("sys.argv", ["publisher", str(result)]),
                mock.patch("sys.stdin", io.StringIO(json.dumps(projection))),
                mock.patch.object(
                    host.urllib.request, "build_opener", return_value=opener
                ),
                mock.patch.object(
                    host.subprocess, "check_output", return_value="b" * 40
                ),
                mock.patch.object(
                    host.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=0, stdout=json.dumps(fixture())),
                ) as producer,
                mock.patch("builtins.print"),
            ):
                host.main()
            request = json.loads(producer.call_args.kwargs["input"])
            self.assertEqual(request["subject"]["configuration_sha"], "b" * 40)
            self.assertNotIn("SYNTHETIC_PRIVATE_PROSE", json.dumps(request))
            self.assertNotIn(
                "SYNTHETIC_TOKEN", json.dumps(producer.call_args.kwargs["env"])
            )
            self.assertTrue(
                (workspace / "output/fullsend-review-evidence.json").is_file()
            )
