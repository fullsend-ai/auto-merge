"""Retain only the bounded v2 record from an authenticated same-run artifact."""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from fullsend_review_evidence import unique_object
from policy_evaluation import require
from review_evidence_contract import validate

MAX_ARCHIVE = 2 * 1024 * 1024
MAX_RECORD = 128 * 1024
MEMBER = "fullsend-review-evidence.json"


def select_attempt_artifact(rows, jobs):
    """Select within the authenticated current attempt's Review execution window."""
    require(len(rows) < 100 and len(jobs) < 100, "retention_metadata_incomplete")
    reviews = [job for job in jobs if job.get("name") == "dispatch / Review"]
    require(
        len(reviews) == 1 and reviews[0].get("conclusion") == "success",
        "retention_review_not_successful",
    )

    def timestamp(value):
        require(isinstance(value, str) and value.endswith("Z"), "retention_invalid_time")
        result = datetime.fromisoformat(value[:-1] + "+00:00")
        require(result.tzinfo == timezone.utc, "retention_invalid_time")
        return result

    start = timestamp(reviews[0].get("started_at"))
    end = timestamp(reviews[0].get("completed_at"))
    require(start <= end, "retention_invalid_time")
    selected = [
        row
        for row in rows
        if row.get("name") == "fullsend-review"
        and start <= timestamp(row.get("created_at")) <= end
    ]
    require(
        len(selected) == 1 and not selected[0].get("expired", True),
        "retention_artifact_ambiguous",
    )
    return selected[0]


def extract_record(raw, metadata, expected_subject, expected_producer):
    require(len(raw) <= MAX_ARCHIVE, "retention_archive_oversized")
    require(
        metadata.get("digest") == "sha256:" + hashlib.sha256(raw).hexdigest(),
        "retention_archive_digest_mismatch",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = archive.infolist()
        selected = [item for item in files if item.filename == MEMBER]
        require(
            0 < len(files) <= 200 and len(selected) == 1, "retention_layout_invalid"
        )
        item = selected[0]
        require(
            not item.is_dir()
            and item.file_size <= MAX_RECORD
            and (item.external_attr >> 16) & 0o170000 != 0o120000,
            "retention_member_invalid",
        )
        # Never extract other members: ordinary runtime output may contain prose.
        raw_record = archive.read(item)
    require(len(raw_record) <= MAX_RECORD, "retention_record_oversized")
    record = json.loads(raw_record, object_pairs_hook=unique_object)
    validate(record)
    require(
        record["schema_version"] == "fullsend-review-evidence/v2",
        "retention_version_invalid",
    )
    require(record["subject"] == expected_subject, "retention_wrong_subject")
    require(record["producer"] == expected_producer, "retention_wrong_producer")
    require(record["completion"] == "completed", "retention_incomplete")
    return raw_record
