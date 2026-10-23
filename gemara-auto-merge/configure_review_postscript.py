#!/usr/bin/env python3
"""Pin a supported Review post-script override; no binary build or network calls."""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "1c0e9b1bef834f5d936119dad8d83b9aa044a598"


def configure(repo=REPO):
    binary = repo / ".fullsend/bin/fullsend"
    if (repo / "bin/fullsend").exists():
        raise ValueError("unexpected_vendored_binary")
    build = json.loads((repo / ".fullsend/local-build.json").read_text())
    if binary.is_symlink() or hashlib.sha256(binary.read_bytes()).hexdigest() != build["binary_sha256"]:
        raise ValueError("vendored_binary_changed")
    publisher = repo / ".fullsend/scripts/publish-review-evidence.py"
    if publisher.is_symlink():
        raise ValueError("symlink_host_source")
    producer = {
        "schema_version": "review-post-script-producer/v1",
        "source_commit": SOURCE_COMMIT,
        "publisher_sha256": hashlib.sha256(publisher.read_bytes()).hexdigest(),
    }
    (repo / ".fullsend/review-evidence-producer.json").write_text(
        json.dumps(producer, indent=2) + "\n"
    )
    paths = sorted(p for p in (repo / ".defaults").rglob("*") if p.is_file())
    paths += sorted((repo / ".github/workflows").glob("reusable-*.yml"))
    paths += [
        repo / name
        for name in [
            ".github/workflows/fullsend.yaml",
            ".fullsend/config.yaml",
            ".fullsend/bin/fullsend",
            ".fullsend/local-build.json",
            "gemara-auto-merge/local-fullsend.patch",
            ".fullsend/harness/review-gemara.yaml",
            ".fullsend/skills/github/SKILL.md",
            ".fullsend/scripts/post-review-gemara.py",
            ".fullsend/scripts/review-risk.patch",
            ".fullsend/scripts/publish-review-evidence.py",
            ".fullsend/scripts/retain-review-evidence.py",
            ".fullsend/providers/gemara-github-ro.yaml",
            "gemara-auto-merge/review_evidence_retention.py",
            "gemara-auto-merge/native_review_artifacts.py",
            ".fullsend/review-evidence-producer.json",
            "gemara-auto-merge/fullsend_review_evidence.py",
            "gemara-auto-merge/review_evidence_contract.py",
            "gemara-auto-merge/policy_evaluation.py",
            "gemara-auto-merge/validate_gemara_artifacts.py",
        ]
    ]
    entries = []
    for path in paths:
        if path.is_symlink():
            raise ValueError("symlink_host_source")
        raw = path.read_bytes()
        entries.append(
            {
                "path": str(path.relative_to(repo)),
                "blob_sha1": hashlib.sha1(
                    b"blob " + str(len(raw)).encode() + b"\0" + raw
                ).hexdigest(),
            }
        )
    (repo / ".fullsend/vendor-evidence-lock.json").write_text(
        json.dumps(
            {
                "schema_version": "review-post-script-host/v1",
                "source_commit": SOURCE_COMMIT,
                "host_files": entries,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "Pinned post-script publisher and",
        len(entries),
        "host files, including the checksum-pinned local Fullsend binary.",
    )


if __name__ == "__main__":
    configure()
