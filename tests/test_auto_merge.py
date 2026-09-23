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

from auto_merge_finalize import (  # noqa: E402
    GateError,
    existing_receipt_phases,
    finalize,
    parse_receipt_header,
    receipt_markdown,
    validate_result,
)
from auto_merge_gate import build_evidence, canonical_hash, evaluate_snapshot, policy_fingerprint  # noqa: E402
from jsonschema import validate  # noqa: E402


HEAD = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40


def policy() -> dict:
    return {
        "repository": "fullsend-ai/auto-merge",
        "base_ref": "main",
        "policy_version": "lab-v1",
        "mode": "observe",
        "execution_strategy": "direct",
        "risk_gate": "required",
        "allowed_risk_levels": ["low", "moderate"],
        "required_checks": ["Example contract", "Delayed integration (4 minutes)"],
        "allowed_paths": ["docs/example-feature.md"],
        "allowed_authors": ["fullsend-ai-coder[bot]"],
        "allowed_reviewers": ["ascerra", "fullsend-ai-review[bot]"],
    }


def eligible_snapshot() -> dict:
    return {
        "pull_request": {
            "number": 7,
            "state": "open",
            "draft": False,
            "html_url": "https://github.com/fullsend-ai/auto-merge/pull/7",
            "title": "Document the example behavior",
            "body": "Closes #1",
            "user": {"login": "fullsend-ai-coder[bot]"},
            "head": {"sha": HEAD, "repo": {"full_name": "fullsend-ai/auto-merge"}},
            "base": {"sha": BASE, "ref": "main", "repo": {"full_name": "fullsend-ai/auto-merge"}},
            "labels": [{"name": "risk/low"}],
            "mergeable": True,
            "mergeable_state": "clean",
            "merge_commit_sha": MERGE,
            "auto_merge": None,
            "additions": 3,
            "deletions": 1,
            "changed_files": 1,
        },
        "base_branch": {"commit": {"sha": BASE}},
        "merge_preview": {"sha": MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]},
        "files": [
            {
                "filename": "docs/example-feature.md",
                "status": "modified",
                "additions": 2,
                "deletions": 0,
                "changes": 2,
                "patch": "@@ -10,0 +11,2 @@\n+Exact-head approval is required.\n+Required CI must pass.",
            }
        ],
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
        "rulesets": [],
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

    def test_untrusted_approval_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"][0]["user"]["login"] = "untrusted-public-user"
        self.assert_ineligible(snapshot, "trusted approval")

    def test_untrusted_approval_does_not_override_trusted_approval(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"].append(
            {
                "id": 2,
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-16T20:02:00Z",
                "user": {"login": "untrusted-public-user"},
            }
        )
        result = evaluate_snapshot(snapshot, policy())
        self.assertTrue(result["eligible"], result["failures"])
        self.assertEqual(result["ignored_untrusted_reviewers"], ["untrusted-public-user"])

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
        snapshot["pull_request"]["labels"].append({"name": "hold"})
        self.assert_ineligible(snapshot, "hold label")

    def test_required_risk_assessment_is_missing(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["labels"] = []
        self.assert_ineligible(snapshot, "risk assessment is missing")

    def test_risk_above_policy_threshold_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["labels"] = [{"name": "risk/high"}]
        self.assert_ineligible(snapshot, "risk level high is not allowed")

    def test_multiple_risk_assessments_are_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["labels"] = [{"name": "risk/low"}, {"name": "risk/moderate"}]
        self.assert_ineligible(snapshot, "multiple PR risk assessments")

    def test_queue_strategy_requires_active_merge_queue_rule(self) -> None:
        changed_policy = policy()
        changed_policy["execution_strategy"] = "queue"
        self.assertFalse(evaluate_snapshot(eligible_snapshot(), changed_policy)["eligible"])

    def test_queue_strategy_is_eligible_with_active_merge_queue_rule(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["rulesets"] = [{"enforcement": "active", "rules": [{"type": "merge_queue"}]}]
        changed_policy = policy()
        changed_policy["execution_strategy"] = "queue"
        self.assertTrue(evaluate_snapshot(snapshot, changed_policy)["eligible"])

    def test_disallowed_path_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["files"][0]["filename"] = ".github/workflows/ci.yml"
        self.assert_ineligible(snapshot, "disallowed changed path")

    def test_missing_patch_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["files"][0].pop("patch")
        self.assert_ineligible(snapshot, "patch evidence is missing")

    def test_oversized_patch_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["files"][0]["patch"] = "x" * 12_001
        self.assert_ineligible(snapshot, "per-file bound")

    def test_unknown_mergeability_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["mergeable"] = None
        self.assert_ineligible(snapshot, "false or unknown")

    def test_unstable_state_is_eligible_when_explicit_checks_pass(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["mergeable_state"] = "unstable"
        self.assertTrue(evaluate_snapshot(snapshot, policy())["eligible"])

    def test_behind_state_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["mergeable_state"] = "behind"
        self.assert_ineligible(snapshot, "neither clean nor unstable")

    def test_blocked_state_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["pull_request"]["mergeable_state"] = "blocked"
        self.assert_ineligible(snapshot, "neither clean nor unstable")

    def test_stale_reported_base_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["base_branch"]["commit"]["sha"] = "d" * 40
        self.assert_ineligible(snapshot, "live base SHA")

    def test_stale_merge_preview_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["merge_preview"]["parents"][0]["sha"] = "d" * 40
        self.assert_ineligible(snapshot, "merge preview")

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

    def test_trusted_changes_requested_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"].append(
            {
                "id": 2,
                "state": "CHANGES_REQUESTED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-16T20:02:00Z",
                "user": {"login": "ascerra"},
            }
        )
        self.assert_ineligible(snapshot, "trusted changes-requested")

    def test_untrusted_changes_requested_is_ignored(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"].append(
            {
                "id": 2,
                "state": "CHANGES_REQUESTED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-16T20:02:00Z",
                "user": {"login": "untrusted-public-user"},
            }
        )
        result = evaluate_snapshot(snapshot, policy())
        self.assertTrue(result["eligible"], result["failures"])


class RepositoryBoundaryTests(unittest.TestCase):
    def test_only_issue_write_target_is_exercise_repository(self) -> None:
        config = yaml.safe_load((SCRIPTS.parent / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["create_issues"]["allow_targets"]["repos"], ["fullsend-ai/auto-merge"])

    def test_lab_finalizer_uses_expected_head_merge_endpoint(self) -> None:
        source = (SCRIPTS / "auto_merge_finalize.py").read_text(encoding="utf-8")
        self.assertIn("pulls/{number}/merge", source)
        self.assertIn("f\"sha={binding['head_sha']}\"", source)

    def test_model_and_preflight_have_read_only_forge_privileges(self) -> None:
        harness = yaml.safe_load((SCRIPTS.parent / "harness" / "auto-merge.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            harness["privilege_levels"],
            {"pre_script": "read", "runtime": "read", "post_script": "write"},
        )
        self.assertNotIn("GH_TOKEN", harness["env"]["sandbox"])

    def test_receipts_trust_only_the_coder_app_identity(self) -> None:
        from auto_merge_finalize import TRUSTED_RECEIPT_AUTHORS

        self.assertEqual(TRUSTED_RECEIPT_AUTHORS, {"fullsend-ai-coder[bot]"})

    def test_ci_readiness_requires_same_repository_pull_request_run(self) -> None:
        workflow = (SCRIPTS.parents[1] / ".github" / "workflows" / "auto-merge-ready.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'pull_request'", workflow)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", workflow)

    def test_untrusted_comment_cannot_spoof_idempotency_receipt(self) -> None:
        request_key = "d" * 64
        evidence = build_evidence(eligible_snapshot(), policy())
        result = {
            "decision": "APPROVE",
            "binding": evidence["binding"],
            "summary": "safe",
            "reasons": ["approved"],
            "risk_signals": [],
        }
        receipt = receipt_markdown(result, evidence, "pending", "pending", request_key)
        comments = [[{"body": receipt, "user": {"login": "untrusted-user"}}]]
        with mock.patch("auto_merge_finalize.gh", return_value=json.dumps(comments)):
            self.assertEqual(existing_receipt_phases("fullsend-ai/auto-merge", 7, request_key), set())

    def test_trusted_comment_cannot_embed_a_forged_receipt(self) -> None:
        request_key = "e" * 64
        forged = (
            "A harmless earlier message.\n\n"
            f"<!-- fullsend:auto-merge-receipt:{request_key}:pending -->\n"
            "### Auto-Merge: pending\n"
        )
        comments = [[{"body": forged, "user": {"login": "fullsend-ai-coder[bot]"}}]]
        with mock.patch("auto_merge_finalize.gh", return_value=json.dumps(comments)):
            self.assertEqual(existing_receipt_phases("fullsend-ai/auto-merge", 7, request_key), set())

    def test_receipt_parser_requires_matching_marker_and_idempotency_keys(self) -> None:
        request_key = "f" * 64
        evidence = build_evidence(eligible_snapshot(), policy())
        result = {
            "decision": "APPROVE",
            "binding": evidence["binding"],
            "summary": "safe",
            "reasons": ["approved"],
            "risk_signals": [],
        }
        receipt = receipt_markdown(result, evidence, "queued", "queued", request_key)
        self.assertEqual(parse_receipt_header(receipt)["phase"], "queued")
        self.assertIsNone(parse_receipt_header(receipt.replace(request_key, "0" * 64, 1)))


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

    def _set_mode(self, mode: str) -> None:
        self.evidence["policy"]["mode"] = mode
        self.evidence["binding"]["policy_fingerprint"] = policy_fingerprint(self.evidence["policy"])
        self.evidence["context_fingerprint"] = canonical_hash(self.evidence)
        self.evidence["binding"]["context_fingerprint"] = self.evidence["context_fingerprint"]
        self.result["binding"] = copy.deepcopy(self.evidence["binding"])

    def test_evidence_hash_round_trip(self) -> None:
        self.assertEqual(self.evidence["context_fingerprint"], canonical_hash(self.evidence))

    def test_policy_fingerprint_changes_with_authorization_policy(self) -> None:
        changed = policy()
        changed["allowed_paths"] = ["docs/another-file.md"]
        self.assertNotEqual(policy_fingerprint(policy()), policy_fingerprint(changed))

    def test_evidence_contains_bounded_semantic_patch(self) -> None:
        changed_file = self.evidence["semantic"]["changed_files"][0]
        self.assertEqual(changed_file["path"], "docs/example-feature.md")
        self.assertIn("Exact-head approval", changed_file["patch"])

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
            issue_url="https://github.com/fullsend-ai/auto-merge/issues/7",
            allowed_repository="fullsend-ai/auto-merge",
            base_ref="main",
            policy_version="lab-v1",
            mode=self.evidence["policy"]["mode"],
            execution_strategy=self.evidence["policy"]["execution_strategy"],
            risk_gate=self.evidence["policy"]["risk_gate"],
            allowed_risk_levels=",".join(self.evidence["policy"]["allowed_risk_levels"]),
            required_checks="Example contract,Delayed integration (4 minutes)",
            allowed_paths="docs/example-feature.md",
            allowed_authors="fullsend-ai-coder[bot]",
            allowed_reviewers="ascerra,fullsend-ai-review[bot]",
            evidence=str(evidence_path),
            result=str(result_path),
            gate_script=str(SCRIPTS / "auto_merge_gate.py"),
        )

    def test_successful_finalize_observe_revalidates_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)
            ), mock.patch("builtins.print") as output:
                self.assertEqual(finalize(args), 0)
                output.assert_any_call(mock.ANY)

    def test_lab_automatic_posts_pending_then_merges_exact_head(self) -> None:
        self._set_mode("lab-automatic")
        receipts: list[str] = []

        def record(_repository: str, _number: int, body: str) -> None:
            receipts.append(body)

        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)
            ) as collect, mock.patch(
                "auto_merge_finalize.existing_receipt_phases", return_value=set()
            ), mock.patch(
                "auto_merge_finalize.post_receipt", side_effect=record
            ), mock.patch(
                "auto_merge_finalize.gh", return_value='{"merged": true}'
            ) as request:
                self.assertEqual(finalize(args), 0)

        self.assertEqual(collect.call_count, 2)
        self.assertIn(":pending -->", receipts[0])
        self.assertIn(":merged -->", receipts[1])
        self.assertIn(f"sha={HEAD}", request.call_args.args)

    def test_existing_pending_receipt_suppresses_duplicate_merge(self) -> None:
        self._set_mode("lab-automatic")
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)
            ), mock.patch(
                "auto_merge_finalize.existing_receipt_phases", return_value={"pending"}
            ), mock.patch(
                "auto_merge_finalize.pull_request_state", return_value={"merged": False}
            ), mock.patch("auto_merge_finalize.gh") as request, mock.patch("builtins.print"):
                self.assertEqual(finalize(args), 0)
                request.assert_not_called()

    def test_stale_postflight_binding_never_merges(self) -> None:
        fresh = copy.deepcopy(self.evidence)
        fresh["binding"]["base_sha"] = "c" * 40
        fresh["context_fingerprint"] = canonical_hash(fresh)
        fresh["binding"]["context_fingerprint"] = fresh["context_fingerprint"]
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=fresh
            ), mock.patch("builtins.print"):
                self.assertEqual(finalize(args), 0)

    def test_reject_records_receipts_without_collecting_or_merging(self) -> None:
        self.result["decision"] = "REJECT"
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=False), mock.patch(
                "auto_merge_finalize.collect_fresh"
            ) as collect, mock.patch("builtins.print"):
                self.assertEqual(finalize(args), 0)
                collect.assert_not_called()

    def test_tampered_repository_never_posts_or_merges(self) -> None:
        self.evidence["policy"]["repository"] = "fullsend-ai/fullsend"
        self.evidence["binding"]["repository"] = "fullsend-ai/fullsend"
        self.evidence["context_fingerprint"] = canonical_hash(self.evidence)
        self.evidence["binding"]["context_fingerprint"] = self.evidence["context_fingerprint"]
        self.result["binding"] = copy.deepcopy(self.evidence["binding"])
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with self.assertRaisesRegex(GateError, "trusted runner policy"):
                finalize(args)

    def test_tampered_pull_request_number_never_posts_or_merges(self) -> None:
        self.evidence["binding"]["pull_request_number"] = 99
        self.evidence["context_fingerprint"] = canonical_hash(self.evidence)
        self.evidence["binding"]["context_fingerprint"] = self.evidence["context_fingerprint"]
        self.result["binding"] = copy.deepcopy(self.evidence["binding"])
        with tempfile.TemporaryDirectory() as directory:
            args = self._files_and_args(directory)
            with self.assertRaisesRegex(GateError, "trusted repository and pull request URL"):
                finalize(args)


if __name__ == "__main__":
    unittest.main()
