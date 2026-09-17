#!/usr/bin/env python3
"""Unit tests for deterministic Auto-Merge gates and model bindings."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock
import yaml


SCRIPTS = Path(__file__).parents[1] / ".fullsend" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from auto_merge_finalize import GateError, finalize, validate_result  # noqa: E402
from auto_merge_gate import build_evidence, canonical_hash, evaluate_snapshot  # noqa: E402
from jsonschema import validate  # noqa: E402


HEAD = "a" * 40
BASE = "b" * 40


def policy() -> dict:
    return {
        "repository": "ascerra/auto-merge",
        "base_ref": "main",
        "policy_version": "lab-v1",
        "required_checks": ["Example contract", "Delayed integration (4 minutes)"],
        "allowed_paths": ["docs/example-feature.md"],
        "allowed_authors": ["fullsend-ai-coder[bot]"],
    }


def eligible_snapshot() -> dict:
    return {
        "pull_request": {
            "number": 7,
            "state": "open",
            "draft": False,
            "html_url": "https://github.com/ascerra/auto-merge/pull/7",
            "title": "Document the example behavior",
            "body": "Closes #1",
            "user": {"login": "fullsend-ai-coder[bot]"},
            "head": {"sha": HEAD, "repo": {"full_name": "ascerra/auto-merge"}},
            "base": {"sha": BASE, "ref": "main", "repo": {"full_name": "ascerra/auto-merge"}},
            "labels": [],
            "mergeable": True,
            "mergeable_state": "clean",
            "auto_merge": None,
            "additions": 3,
            "deletions": 1,
            "changed_files": 1,
        },
        "files": [{"filename": "docs/example-feature.md"}],
        "reviews": [
            {
                "id": 1,
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-16T20:00:00Z",
                "user": {"login": "fullsend-ai-review[bot]"},
            }
        ],
        "commits": [
            {
                "sha": HEAD,
                "commit": {"message": "docs: update example\n\nSigned-off-by: Fullsend Coder <coder@example.test>"},
            }
        ],
        "check_runs": [
            {"id": 1, "name": "Example contract", "status": "completed", "conclusion": "success", "head_sha": HEAD, "completed_at": "2026-09-16T20:01:00Z"},
            {"id": 2, "name": "Delayed integration (4 minutes)", "status": "completed", "conclusion": "success", "head_sha": HEAD, "completed_at": "2026-09-16T20:05:00Z"},
        ],
        "review_threads": {"nodes": [], "pageInfo": {"hasNextPage": False}},
    }


class GateTests(unittest.TestCase):
    def assert_ineligible(self, snapshot: dict, phrase: str) -> None:
        result = evaluate_snapshot(snapshot, policy())
        self.assertFalse(result["eligible"])
        self.assertTrue(any(phrase in failure for failure in result["failures"]), result["failures"])

    def test_eligible_snapshot(self) -> None:
        self.assertTrue(evaluate_snapshot(eligible_snapshot(), policy())["eligible"])

    def test_stale_approval_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"][0]["commit_id"] = "c" * 40
        self.assert_ineligible(snapshot, "exact head SHA")

    def test_pending_check_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["check_runs"][0].update(status="in_progress", conclusion=None)
        self.assert_ineligible(snapshot, "pending")

    def test_failed_check_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["check_runs"][1]["conclusion"] = "failure"
        self.assert_ineligible(snapshot, "did not succeed")

    def test_hold_label_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["labels"] = [{"name": "hold"}]
        self.assert_ineligible(snapshot, "hold label")

    def test_disallowed_path_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["files"] = [{"filename": ".github/workflows/ci.yml"}]
        self.assert_ineligible(snapshot, "disallowed changed path")

    def test_unknown_mergeability_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["mergeable"] = None
        self.assert_ineligible(snapshot, "false or unknown")

    def test_native_auto_merge_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["auto_merge"] = {"enabled_by": {"login": "someone"}}
        self.assert_ineligible(snapshot, "standing auto-merge")

    def test_unsigned_commit_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["commits"][0]["commit"]["message"] = "docs: update example"
        self.assert_ineligible(snapshot, "DCO sign-off")

    def test_unresolved_thread_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["review_threads"]["nodes"] = [{"isResolved": False}]
        self.assert_ineligible(snapshot, "unresolved review thread")

    def test_changes_requested_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"].append(
            {
                "id": 2,
                "state": "CHANGES_REQUESTED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-16T20:02:00Z",
                "user": {"login": "human-reviewer"},
            }
        )
        self.assert_ineligible(snapshot, "changes-requested")


class RepositoryBoundaryTests(unittest.TestCase):
    def test_only_issue_write_target_is_exercise_repository(self) -> None:
        config = yaml.safe_load((SCRIPTS.parent / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["create_issues"]["allow_targets"]["repos"], ["ascerra/auto-merge"])


class BindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = build_evidence(eligible_snapshot(), policy())
        self.result = {
            "decision": "APPROVE",
            "binding": copy.deepcopy(self.evidence["binding"]),
            "summary": "The bounded documentation change is safe to merge",
            "reasons": ["The change matches the issue and required checks passed"],
            "risk_signals": [],
        }

    def test_evidence_hash_round_trip(self) -> None:
        self.assertEqual(self.evidence["evidence_sha256"], canonical_hash(self.evidence))

    def test_valid_result(self) -> None:
        validate_result(self.result, self.evidence)
        schema = json.loads((SCRIPTS.parent / "schemas" / "auto-merge-result.schema.json").read_text())
        validate(instance=self.result, schema=schema)

    def test_stale_model_binding_is_rejected(self) -> None:
        self.result["binding"]["head_sha"] = "c" * 40
        with self.assertRaisesRegex(GateError, "does not exactly match"):
            validate_result(self.result, self.evidence)

    def test_approve_with_risk_is_rejected(self) -> None:
        self.result["risk_signals"] = ["Needs human judgment"]
        with self.assertRaisesRegex(GateError, "cannot contain risk"):
            validate_result(self.result, self.evidence)

    def test_invalid_decision_is_rejected(self) -> None:
        self.result["decision"] = "MERGE"
        with self.assertRaisesRegex(GateError, "decision is invalid"):
            validate_result(self.result, self.evidence)

    def _files_and_args(self, directory: str) -> SimpleNamespace:
        evidence_path = Path(directory) / "evidence.json"
        result_path = Path(directory) / "result.json"
        evidence_path.write_text(json.dumps(self.evidence), encoding="utf-8")
        result_path.write_text(json.dumps(self.result), encoding="utf-8")
        return SimpleNamespace(
            issue_url="https://github.com/ascerra/auto-merge/issues/7",
            allowed_repository="ascerra/auto-merge",
            base_ref="main",
            policy_version="lab-v1",
            required_checks="Example contract,Delayed integration (4 minutes)",
            allowed_paths="docs/example-feature.md",
            allowed_authors="fullsend-ai-coder[bot]",
            evidence=str(evidence_path),
            result=str(result_path),
            gate_script=str(SCRIPTS / "auto_merge_gate.py"),
        )

    def test_successful_finalize_uses_exact_head_after_receipt(self) -> None:
        events: list[str] = []

        def receipt(*_args, **_kwargs) -> None:
            events.append("receipt")

        def merge(*args, **_kwargs) -> str:
            events.append("merge")
            self.assertIn(f"sha={HEAD}", args)
            return '{"merged": true}'

        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.post_receipt", side_effect=receipt
            ), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)
            ), mock.patch("auto_merge_finalize.gh", side_effect=merge):
                self.assertEqual(finalize(args), 0)

        self.assertEqual(events[0:2], ["receipt", "merge"])

    def test_stale_postflight_binding_never_merges(self) -> None:
        fresh = copy.deepcopy(self.evidence)
        fresh["binding"]["base_sha"] = "c" * 40
        fresh["evidence_sha256"] = canonical_hash(fresh)
        fresh["binding"]["evidence_sha256"] = fresh["evidence_sha256"]
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.post_receipt"
            ) as receipt, mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=fresh
            ), mock.patch("auto_merge_finalize.gh") as merge:
                self.assertEqual(finalize(args), 0)
                merge.assert_not_called()
                self.assertEqual(receipt.call_count, 2)

    def test_reject_records_receipts_without_collecting_or_merging(self) -> None:
        self.result["decision"] = "REJECT"
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.post_receipt"
            ) as receipt, mock.patch("auto_merge_finalize.collect_fresh") as collect, mock.patch(
                "auto_merge_finalize.gh"
            ) as merge:
                self.assertEqual(finalize(args), 0)
                self.assertEqual(receipt.call_count, 2)
                collect.assert_not_called()
                merge.assert_not_called()

    def test_tampered_repository_never_posts_or_merges(self) -> None:
        self.evidence["policy"]["repository"] = "fullsend-ai/fullsend"
        self.evidence["binding"]["repository"] = "fullsend-ai/fullsend"
        self.evidence["evidence_sha256"] = canonical_hash(self.evidence)
        self.evidence["binding"]["evidence_sha256"] = self.evidence["evidence_sha256"]
        self.result["binding"] = copy.deepcopy(self.evidence["binding"])
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch("auto_merge_finalize.post_receipt") as receipt, mock.patch(
                "auto_merge_finalize.gh"
            ) as merge:
                with self.assertRaisesRegex(GateError, "trusted runner policy"):
                    finalize(args)
                receipt.assert_not_called()
                merge.assert_not_called()

    def test_tampered_pull_request_number_never_posts_or_merges(self) -> None:
        self.evidence["binding"]["pull_request_number"] = 99
        self.evidence["evidence_sha256"] = canonical_hash(self.evidence)
        self.evidence["binding"]["evidence_sha256"] = self.evidence["evidence_sha256"]
        self.result["binding"] = copy.deepcopy(self.evidence["binding"])
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch("auto_merge_finalize.post_receipt") as receipt, mock.patch(
                "auto_merge_finalize.gh"
            ) as merge:
                with self.assertRaisesRegex(GateError, "trusted repository and pull request URL"):
                    finalize(args)
                receipt.assert_not_called()
                merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
