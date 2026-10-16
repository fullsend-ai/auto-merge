import hashlib
import io
import json
import unittest
from unittest import mock
import urllib.error
import zipfile

import native_review_artifacts as n
from policy_evaluation import InputError
from test_review_evidence_contract import fixture
from run_review_evidence_examples import NOW


def archive(record, name="fullsend-review-evidence.json"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(name, json.dumps(record))
    return stream.getvalue()


class NativeArtifactTests(unittest.TestCase):
    def setUp(self):
        self.record = fixture()
        self.run = {
            "id": 1234,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/fullsend.yaml",
            "workflow_id": 365189947,
            "repository": {"full_name": "fullsend-ai/auto-merge"},
            "head_repository": {"full_name": "fullsend-ai/auto-merge"},
            "referenced_workflows": [
                {
                    "path": "fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@" + self.record["producer"]["fullsend_commit"],
                    "sha": self.record["producer"]["fullsend_commit"],
                },
            ],
        }
        self.raw = archive(self.record)
        self.metadata = {
            "id": 123,
            "name": "fullsend-review-evidence-1",
            "expired": False,
            "digest": "sha256:" + hashlib.sha256(self.raw).hexdigest(),
        }
        self.pr = {
            "number": 999001,
            "head": {"sha": "a" * 40},
            "base": {"sha": "b" * 40},
        }
        self.client = mock.Mock()
        self.client.get.return_value = self.run
        self.build = {
            "source_commit": self.record["producer"]["fullsend_commit"],
            "overlay_sha256": self.record["producer"]["overlay_sha256"],
        }

    def verify(self, run=None, context=True):
        with mock.patch.object(n, "host_sources", return_value=self.build):
            return n.verify_record(
                self.client,
                {},
                self.pr,
                self.run if run is None else run,
                self.metadata,
                self.raw,
                lambda *_: context,
                NOW,
            )

    def test_authenticated_run_metadata_and_context_are_required(self):
        self.assertEqual(self.verify()["reason"], "contract_verified")
        for change in [
            {"conclusion": "failure"},
            {"run_attempt": 2},
            {"workflow_id": 1},
            {"referenced_workflows": []},
        ]:
            with self.assertRaises(InputError):
                self.verify(dict(self.run, **change))
        with self.assertRaises(InputError):
            self.verify(context=False)

    def test_unpinned_or_additional_workflow_wrapper_is_rejected(self):
        refs = self.run["referenced_workflows"]
        for changed in [
            [],
            refs + [dict(refs[0])],
            [dict(refs[0], sha="f" * 40)],
            [dict(refs[0], path="other/repo/.github/workflows/reusable-dispatch.yml@main")],
            [dict(refs[0], path=refs[0]["path"].split("@", 1)[0] + "@main")],
        ]:
            with self.assertRaises(InputError):
                self.verify(dict(self.run, referenced_workflows=changed))

    def test_zip_digest_exact_member_and_json_contract_fail_closed(self):
        for raw, metadata in [
            (self.raw, dict(self.metadata, digest="sha256:" + "f" * 64)),
            (archive(self.record, "../fullsend-review-evidence.json"), None),
            (archive(dict(self.record, trusted=True)), None),
        ]:
            metadata = metadata or dict(
                self.metadata, digest="sha256:" + hashlib.sha256(raw).hexdigest()
            )
            with self.assertRaises(InputError):
                n.decode_artifact(raw, metadata)

    def test_later_running_or_failed_run_does_not_reuse_older_approval(self):
        for status in [{"status": "in_progress"}, {"conclusion": "cancelled"}]:
            self.client.pages.return_value = [
                dict(self.run, id=1235, **status),
                self.run,
            ]
            result = n.observe(
                self.client,
                {},
                self.pr,
                lambda *_: True,
                NOW,
                fetch=lambda _: self.fail("must not download stale approval"),
            )
            self.assertIsNone(result["values"]["AM-FINDINGS"])

    def test_download_does_not_forward_token_to_the_blob_redirect(self):
        opener = mock.MagicMock()
        redirect = urllib.error.HTTPError(
            "https://api.github.com/",
            302,
            "redirect",
            {
                "Location": "https://productionresults.blob.core.windows.net/a?sig=TEST_SIGNATURE"
            },
            None,
        )
        response = mock.MagicMock()
        response.read.return_value = self.raw
        opener.open.side_effect = [redirect, response]
        with (
            mock.patch.object(n.urllib.request, "build_opener", return_value=opener),
            mock.patch.dict("os.environ", {"GH_TOKEN": "SYNTHETIC_TOKEN"}),
        ):
            self.assertEqual(n.download(123), self.raw)
        first, second = [call.args[0] for call in opener.open.call_args_list]
        self.assertIn("Authorization", first.headers)
        self.assertNotIn("Authorization", second.headers)

    def test_redirect_to_other_host_is_refused_without_following_it(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://api.github.com/",
            302,
            "redirect",
            {"Location": "https://attacker.example/path"},
            None,
        )
        with (
            mock.patch.object(n.urllib.request, "build_opener", return_value=opener),
            self.assertRaises(InputError),
        ):
            n.download(123)
        self.assertEqual(opener.open.call_count, 1)
