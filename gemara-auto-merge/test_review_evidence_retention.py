import copy
import hashlib
import io
import json
import unittest
import warnings
import zipfile

from policy_evaluation import ROOT, InputError, digest, load
from review_evidence_contract import encode_post_script
from review_evidence_retention import extract_record
from run_review_evidence_examples import synthetic_input


def archive(value, extra=None, duplicate=False):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as zipped:
        zipped.writestr("fullsend-review-evidence.json", value)
        if extra:
            zipped.writestr("unrestricted-runtime-output.txt", extra)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                zipped.writestr("fullsend-review-evidence.json", value)
    raw = raw.getvalue()
    return raw, {"digest": "sha256:" + hashlib.sha256(raw).hexdigest()}


class RetentionTests(unittest.TestCase):
    def setUp(self):
        value = synthetic_input()
        value["producer"].pop("overlay_sha256", None)
        value["producer"].update(
            kind="fullsend-post-script-lab",
            publisher_sha256=load(
                ROOT.parent / ".fullsend/review-evidence-producer.json"
            )["publisher_sha256"],
        )
        self.record = json.loads(encode_post_script(value))
        self.value = (json.dumps(self.record) + "\n").encode()

    def extract(self, raw, metadata):
        return extract_record(
            raw, metadata, self.record["subject"], self.record["producer"]
        )

    def test_retains_exact_bounded_bytes_without_extracting_other_runtime_output(self):
        raw, metadata = archive(self.value, b"PRIVATE_OUTPUT_MUST_NOT_BE_RETAINED")
        self.assertEqual(self.extract(raw, metadata), self.value)
        self.assertNotIn(b"PRIVATE_OUTPUT", self.extract(raw, metadata))

    def test_rejects_altered_archive_and_duplicate_record(self):
        raw, metadata = archive(self.value)
        with self.assertRaises(InputError):
            self.extract(raw, dict(metadata, digest="sha256:" + "0" * 64))
        raw, metadata = archive(self.value, duplicate=True)
        with self.assertRaises(InputError):
            self.extract(raw, metadata)

    def test_rejects_wrong_revision_run_attempt_and_publisher_even_with_valid_self_digest(
        self,
    ):
        for section, key, value in [
            ("subject", "head_sha", "f" * 40),
            ("producer", "run_id", 9999),
            ("producer", "run_attempt", 2),
            ("producer", "publisher_sha256", "f" * 64),
        ]:
            with self.subTest(key=key):
                record = copy.deepcopy(self.record)
                record[section][key] = value
                record["payload_sha256"] = digest(
                    {k: v for k, v in record.items() if k != "payload_sha256"}
                )
                raw, metadata = archive(json.dumps(record))
                with self.assertRaises(InputError):
                    self.extract(raw, metadata)

    def test_rejects_oversized_member_and_missing_record(self):
        raw, metadata = archive(b"x" * (128 * 1024 + 1))
        with self.assertRaises(InputError):
            self.extract(raw, metadata)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("agent-result.json", "{}")
        raw = buffer.getvalue()
        with self.assertRaises(InputError):
            self.extract(raw, {"digest": "sha256:" + hashlib.sha256(raw).hexdigest()})
