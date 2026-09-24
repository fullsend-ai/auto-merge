#!/usr/bin/env python3
"""Tests for SCM-native Auto-Merge semantic authorization."""

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
from jsonschema import validate


SCRIPTS = Path(__file__).parents[1] / ".fullsend" / "scripts"
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

from auto_merge_finalize import (  # noqa: E402
    GateError,
    existing_receipt_phases,
    finalize,
    gh,
    parse_receipt_header,
    receipt_markdown,
    validate_result,
)
from auto_merge_gate import build_evidence, canonical_hash, evaluate_snapshot, policy_fingerprint  # noqa: E402


HEAD = "a" * 40
BASE = "b" * 40
def policy(**overrides: object) -> dict:
    result = {
        "repository": "fullsend-ai/auto-merge",
        "base_ref": "main",
        "policy_version": "lab-v3-scm-native",
        "mode": "observe",
        "semantic_reviewer": "fullsend-ai-review[bot]",
        "risk_assessment_producer": "fullsend-ai-review[bot]",
        "artifact_correlation_minutes": 1,
        "maximum_unattended_risk": "moderate",
        "human_signal_associations": ["COLLABORATOR", "MEMBER", "OWNER"],
        "review_quality_mode": "off",
        "review_quality_minimum_score": 0.98,
        "review_quality_minimum_samples": 50,
        "custom_instructions": "Do not authorize when trusted human context contains an unresolved request to pause, sequencing requirement, or required follow-up.",
    }
    result.update(overrides)
    return result


def risk_comment(level: str = "low", score: int = 1, *, comment_id: int = 101) -> dict:
    return {
        "id": comment_id,
        "body": (
            "<!-- fullsend:risk-assessment -->\n"
            f"**Risk Assessment: {level} ({score}/5)**\n\n"
            "Documentation-only change with no security, dependency, or deployment impact."
        ),
        "created_at": "2026-09-23T20:00:04Z",
        "updated_at": "2026-09-23T20:00:04Z",
        "author_association": "NONE",
        "user": {"login": "fullsend-ai-review[bot]", "type": "Bot"},
    }


def review_summary_comment(*, head: str = HEAD, comment_id: int = 102) -> dict:
    return {
        "id": comment_id,
        "body": f"<!-- fullsend:review-agent -->\n<!-- **Head SHA:** {head} -->\n\nLooks good to me",
        "created_at": "2026-09-23T20:00:05Z",
        "updated_at": "2026-09-23T20:00:05Z",
        "author_association": "NONE",
        "user": {"login": "fullsend-ai-review[bot]", "type": "Bot"},
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
            "user": {"login": "fullsend-ai-coder[bot]", "type": "Bot"},
            "head": {"sha": HEAD, "repo": {"full_name": "fullsend-ai/auto-merge"}},
            "base": {"sha": BASE, "ref": "main", "repo": {"full_name": "fullsend-ai/auto-merge"}},
        },
        "base_branch": {"commit": {"sha": BASE}},
        "files": [
            {"filename": "docs/example-feature.md", "status": "modified", "additions": 4, "deletions": 1, "changes": 5},
        ],
        "comments": [risk_comment(), review_summary_comment()],
        "reviews": [
            {
                "id": 201,
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-23T20:00:06Z",
                "author_association": "NONE",
                "body": "Review approved the exact revision.",
                "user": {"login": "fullsend-ai-review[bot]", "type": "Bot"},
            }
        ],
        "review_quality": {},
    }


def human_comment(body: str, *, comment_id: int = 301, author: str = "ascerra", association: str = "OWNER") -> dict:
    return {
        "id": comment_id,
        "body": body,
        "created_at": "2026-09-23T20:01:00Z",
        "updated_at": "2026-09-23T20:01:00Z",
        "author_association": association,
        "user": {"login": author, "type": "User"},
    }


def result_for(evidence: dict, decision: str = "AUTHORIZE", blockers: list[str] | None = None) -> dict:
    return {
        "decision": decision,
        "binding": copy.deepcopy(evidence["binding"]),
        "summary": "Semantic context permits unattended merge",
        "reasons": ["Review, risk, and human context support unattended merge"],
        "blocking_signals": blockers or [],
        "evidence_comment_ids": [101],
    }


class SemanticGateTests(unittest.TestCase):
    def assert_not_ready(self, snapshot: dict, phrase: str, changed_policy: dict | None = None) -> None:
        evaluation = evaluate_snapshot(snapshot, changed_policy or policy())
        self.assertFalse(evaluation["ready_for_semantic_evaluation"])
        self.assertTrue(any(phrase in failure for failure in evaluation["failures"]), evaluation["failures"])

    def test_ready_snapshot_checks_semantics_not_scm_policy(self) -> None:
        snapshot = eligible_snapshot()
        evaluation = evaluate_snapshot(snapshot, policy())
        self.assertTrue(evaluation["ready_for_semantic_evaluation"], evaluation["failures"])
        self.assertFalse(evaluation["scm_policy_checked"])
        self.assertNotIn("check_runs", snapshot)
        self.assertNotIn("rulesets", snapshot)
        self.assertNotIn("mergeable", snapshot["pull_request"])

    def test_stale_review_attestation_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"][0]["commit_id"] = "d" * 40
        self.assert_not_ready(snapshot, "Review Agent attestation")

    def test_human_approval_cannot_impersonate_review_agent(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["reviews"][0]["user"] = {"login": "ascerra", "type": "User"}
        self.assert_not_ready(snapshot, "Review Agent attestation")

    def test_missing_or_unbound_risk_artifact_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"] = [review_summary_comment()]
        self.assert_not_ready(snapshot, "risk assessment")
        snapshot = eligible_snapshot()
        snapshot["comments"][0]["updated_at"] = "2026-09-23T19:00:00Z"
        self.assert_not_ready(snapshot, "risk assessment")

    def test_review_summary_must_bind_the_exact_head(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"][1] = review_summary_comment(head="d" * 40)
        self.assert_not_ready(snapshot, "Review summary")

    def test_current_review_summary_preserves_bounded_reviewer_words(self) -> None:
        snapshot = eligible_snapshot()
        summary = evaluate_snapshot(snapshot, policy())["semantic_context"]["review_summary"]
        self.assertEqual(summary["status"], "CURRENT")
        self.assertIn("Looks good to me", summary["summary"])
        self.assertNotIn("fullsend:review-agent", summary["summary"])
        self.assertNotIn("Head SHA", summary["summary"])

    def test_evidence_contains_intent_and_bounded_change_context(self) -> None:
        evidence = build_evidence(eligible_snapshot(), policy())
        self.assertEqual(evidence["intent"]["title"], "Document the example behavior")
        self.assertEqual(evidence["change_context"]["files"][0]["filename"], "docs/example-feature.md")
        self.assertEqual(evidence["change_context"]["additions"], 4)
        self.assertEqual(evidence["trace_refs"], [])

    def test_trace_references_are_optional_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace-refs.json"
            path.write_text(json.dumps({"refs": [{"agent": "code", "trace_id": "trace-123", "purpose": "implementation evidence"}]}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"AUTO_MERGE_TRACE_REFS_FILE": str(path)}):
                evidence = build_evidence(eligible_snapshot(), policy())
        self.assertEqual(evidence["trace_refs"][0]["trace_id"], "trace-123")

    def test_review_summary_text_is_bounded(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"][1]["body"] += "\n" + ("x" * 10_000)
        summary = evaluate_snapshot(snapshot, policy())["semantic_context"]["review_summary"]
        self.assertEqual(len(summary["summary"]), 4_000)

    def test_risk_above_repository_semantic_policy_is_rejected(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"] = [risk_comment("high", 4), review_summary_comment()]
        self.assert_not_ready(snapshot, "exceeds unattended policy")

    def test_human_veto_is_agent_evidence_not_a_preflight_keyword_gate(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"].append(human_comment("Please do not merge until the release owner confirms sequencing."))
        evaluation = evaluate_snapshot(snapshot, policy())
        self.assertTrue(evaluation["ready_for_semantic_evaluation"], evaluation["failures"])
        signal = evaluation["semantic_context"]["human_signals"][0]
        self.assertTrue(signal["trusted_actor"])
        self.assertIn("do not merge", signal["body"])

    def test_untrusted_human_context_is_identified_but_not_discarded(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"].append(human_comment("This may require coordination.", author="outsider", association="NONE"))
        signal = evaluate_snapshot(snapshot, policy())["semantic_context"]["human_signals"][0]
        self.assertFalse(signal["trusted_actor"])

    def test_control_commands_and_machine_receipts_are_not_human_context(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"].extend(
            [
                human_comment("/fs-auto-merge", comment_id=302),
                human_comment("<!-- fullsend:auto-merge-receipt:" + "f" * 64 + ":pending -->", comment_id=303),
            ]
        )
        self.assertEqual(evaluate_snapshot(snapshot, policy())["semantic_context"]["human_signals"], [])

    def test_optional_review_quality_modes(self) -> None:
        snapshot = eligible_snapshot()
        self.assertTrue(evaluate_snapshot(snapshot, policy(review_quality_mode="off"))["ready_for_semantic_evaluation"])
        self.assertTrue(evaluate_snapshot(snapshot, policy(review_quality_mode="observe"))["ready_for_semantic_evaluation"])
        self.assert_not_ready(snapshot, "unavailable", policy(review_quality_mode="enforce"))
        snapshot["review_quality"] = {"score": 0.97, "sample_count": 80, "metric": "review_correctly_approved"}
        self.assert_not_ready(snapshot, "below", policy(review_quality_mode="enforce"))
        snapshot["review_quality"] = {"score": 0.99, "sample_count": 80, "metric": "review_correctly_approved"}
        self.assertTrue(evaluate_snapshot(snapshot, policy(review_quality_mode="enforce"))["ready_for_semantic_evaluation"])

    def test_semantic_fingerprint_changes_with_human_context(self) -> None:
        before = build_evidence(eligible_snapshot(), policy())["binding"]["semantic_fingerprint"]
        snapshot = eligible_snapshot()
        snapshot["comments"].append(human_comment("Please wait for rollout coordination."))
        after = build_evidence(snapshot, policy())["binding"]["semantic_fingerprint"]
        self.assertNotEqual(before, after)

    def test_outsider_flood_cannot_evict_trusted_pause(self) -> None:
        snapshot = eligible_snapshot()
        snapshot["comments"].append(human_comment("Please do not merge yet.", comment_id=300))
        for index in range(150):
            snapshot["comments"].append(
                human_comment(
                    f"Outsider context {index}",
                    comment_id=1_000 + index,
                    author=f"outsider-{index}",
                    association="NONE",
                )
            )
        context = evaluate_snapshot(snapshot, policy())["semantic_context"]
        self.assertTrue(any(signal["id"] == 300 for signal in context["human_signals"]))
        self.assertTrue(context["human_signal_integrity"]["untrusted_truncated"])

    def test_trusted_context_overflow_fails_closed(self) -> None:
        snapshot = eligible_snapshot()
        for index in range(101):
            snapshot["comments"].append(human_comment(f"Trusted context {index}", comment_id=2_000 + index))
        self.assert_not_ready(snapshot, "trusted human context exceeds")


class BindingAndFinalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = build_evidence(eligible_snapshot(), policy())
        self.result = result_for(self.evidence)

    def args(self, directory: str) -> SimpleNamespace:
        evidence_path = Path(directory) / "evidence.json"
        result_path = Path(directory) / "result.json"
        evidence_path.write_text(json.dumps(self.evidence), encoding="utf-8")
        result_path.write_text(json.dumps(self.result), encoding="utf-8")
        configured = self.evidence["policy"]
        return SimpleNamespace(
            issue_url="https://github.com/fullsend-ai/auto-merge/pull/7",
            allowed_repository=configured["repository"],
            base_ref=configured["base_ref"],
            policy_version=configured["policy_version"],
            mode=configured["mode"],
            semantic_reviewer=configured["semantic_reviewer"],
            risk_assessment_producer=configured["risk_assessment_producer"],
            artifact_correlation_minutes=configured["artifact_correlation_minutes"],
            maximum_unattended_risk=configured["maximum_unattended_risk"],
            human_signal_associations=",".join(configured["human_signal_associations"]),
            review_quality_mode=configured["review_quality_mode"],
            review_quality_minimum_score=configured["review_quality_minimum_score"],
            review_quality_minimum_samples=configured["review_quality_minimum_samples"],
            review_quality_file="",
            custom_instructions=configured["custom_instructions"],
            evidence=str(evidence_path),
            result=str(result_path),
            gate_script=str(SCRIPTS / "auto_merge_gate.py"),
        )

    def test_evidence_and_result_schema_round_trip(self) -> None:
        self.assertEqual(self.evidence["context_fingerprint"], canonical_hash(self.evidence))
        validate_result(self.result, self.evidence)
        schema = json.loads((ROOT / ".fullsend/schemas/auto-merge-result.schema.json").read_text())
        validate(instance=self.result, schema=schema)

    def test_policy_fingerprint_changes_with_semantic_policy(self) -> None:
        self.assertNotEqual(policy_fingerprint(policy()), policy_fingerprint(policy(maximum_unattended_risk="low")))

    def test_stale_or_tampered_binding_is_rejected(self) -> None:
        self.result["binding"]["head_sha"] = "d" * 40
        with self.assertRaisesRegex(GateError, "does not exactly match"):
            validate_result(self.result, self.evidence)

    def test_authorize_cannot_report_blockers(self) -> None:
        self.result["blocking_signals"] = ["Active human veto"]
        with self.assertRaisesRegex(GateError, "cannot contain blocking"):
            validate_result(self.result, self.evidence)

    def test_duplicate_evidence_comment_ids_are_rejected(self) -> None:
        self.result["evidence_comment_ids"] = [101, 101]
        with self.assertRaisesRegex(GateError, "evidence_comment_ids are invalid"):
            validate_result(self.result, self.evidence)

    def test_github_operations_require_host_token(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(GateError, "GH_TOKEN is required"):
                gh("api", "user")
            run.assert_not_called()

    def test_observe_mode_revalidates_without_scm_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)), mock.patch(
                "auto_merge_finalize.gh"
            ) as scm, mock.patch("builtins.print"):
                self.assertEqual(finalize(self.args(directory)), 0)
                scm.assert_not_called()

    def test_defer_records_semantic_outcome_without_scm_request(self) -> None:
        self.result = result_for(self.evidence, "DEFER", ["Release owner asked the team to wait"])
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("auto_merge_finalize.collect_fresh") as collect, mock.patch("auto_merge_finalize.gh") as scm, mock.patch(
                "builtins.print"
            ):
                self.assertEqual(finalize(self.args(directory)), 0)
                collect.assert_not_called()
                scm.assert_not_called()

    def test_lab_mode_submits_exact_head_to_native_auto_merge(self) -> None:
        changed_policy = policy(mode="lab-automatic")
        self.evidence = build_evidence(eligible_snapshot(), changed_policy)
        self.result = result_for(self.evidence)
        receipts: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("auto_merge_finalize.collect_fresh", return_value=copy.deepcopy(self.evidence)) as collect, mock.patch(
                "auto_merge_finalize.existing_receipt_phases", return_value=set()
            ), mock.patch("auto_merge_finalize.post_receipt", side_effect=lambda _r, _n, body: receipts.append(body)), mock.patch(
                "auto_merge_finalize.gh", return_value=""
            ) as scm:
                self.assertEqual(finalize(self.args(directory)), 0)
        self.assertEqual(collect.call_count, 2)
        self.assertIn(":pending -->", receipts[0])
        self.assertIn(":submitted -->", receipts[1])
        scm.assert_called_once_with(
            "pr", "merge", "7", "--repo", "fullsend-ai/auto-merge", "--auto", "--squash", "--match-head-commit", HEAD
        )

    def test_changed_semantic_context_aborts_before_scm_request(self) -> None:
        changed_policy = policy(mode="lab-automatic")
        self.evidence = build_evidence(eligible_snapshot(), changed_policy)
        self.result = result_for(self.evidence)
        changed = eligible_snapshot()
        changed["comments"].append(human_comment("Please stop; rollout coordination is unresolved."))
        fresh = build_evidence(changed, changed_policy)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("auto_merge_finalize.existing_receipt_phases", return_value=set()), mock.patch(
                "auto_merge_finalize.collect_fresh", return_value=fresh
            ), mock.patch(
                "auto_merge_finalize.post_receipt"
            ), mock.patch("auto_merge_finalize.gh") as scm:
                self.assertEqual(finalize(self.args(directory)), 0)
                scm.assert_not_called()

    def test_pending_receipt_reconciles_active_request_without_resubmission(self) -> None:
        changed_policy = policy(mode="lab-automatic")
        self.evidence = build_evidence(eligible_snapshot(), changed_policy)
        self.result = result_for(self.evidence)
        receipts: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("auto_merge_finalize.existing_receipt_phases", return_value={"pending"}), mock.patch(
                "auto_merge_finalize.native_request_state", return_value="active"
            ), mock.patch("auto_merge_finalize.post_receipt", side_effect=lambda _r, _n, body: receipts.append(body)), mock.patch(
                "auto_merge_finalize.collect_fresh"
            ) as collect, mock.patch("auto_merge_finalize.gh") as scm:
                self.assertEqual(finalize(self.args(directory)), 0)
                collect.assert_not_called()
                scm.assert_not_called()
        self.assertIn(":submitted -->", receipts[0])


class RepositoryBoundaryTests(unittest.TestCase):
    def test_only_issue_write_target_is_exercise_repository(self) -> None:
        config = yaml.safe_load((ROOT / ".fullsend/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["create_issues"]["allow_targets"]["repos"], ["fullsend-ai/auto-merge"])

    def test_model_and_pre_script_have_read_only_forge_privileges(self) -> None:
        harness = yaml.safe_load((ROOT / ".fullsend/harness/auto-merge.yaml").read_text(encoding="utf-8"))
        self.assertEqual(harness["privilege_levels"], {"pre_script": "read", "runtime": "read", "post_script": "write"})
        self.assertNotIn("GH_TOKEN", harness["env"]["sandbox"])

    def test_removed_readiness_workflow_cannot_duplicate_ci_scheduling(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/auto-merge-ready.yml").exists())

    def test_harness_is_self_contained_and_queue_gate_is_not_required(self) -> None:
        harness = yaml.safe_load((ROOT / ".fullsend/harness/auto-merge.yaml").read_text(encoding="utf-8"))
        ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        self.assertNotIn("queue-authorization", ci["jobs"])
        self.assertEqual(harness["trigger"].count("review_submitted"), 1)
        self.assertIn('event.actor.id == "fullsend-ai-review[bot]"', harness["trigger"])
        self.assertFalse((ROOT / ".fullsend/scripts/auto_merge_queue_gate.py").exists())

    def test_collector_does_not_fetch_scm_policy_surfaces(self) -> None:
        source = (SCRIPTS / "auto_merge_gate.py").read_text(encoding="utf-8")
        for duplicate in ("check-runs", "/rulesets", "mergeable_state", "reviewThreads", "required_checks"):
            self.assertNotIn(duplicate, source)

    def test_untrusted_comment_cannot_spoof_receipt(self) -> None:
        evidence = build_evidence(eligible_snapshot(), policy())
        request_key = "d" * 64
        receipt = receipt_markdown(result_for(evidence), evidence, "pending", "pending", request_key)
        comments = [[{"body": receipt, "user": {"login": "untrusted-user"}}]]
        with mock.patch("auto_merge_finalize.gh", return_value=json.dumps(comments)):
            self.assertEqual(existing_receipt_phases("fullsend-ai/auto-merge", 7, request_key), set())

    def test_receipt_lookup_scans_all_pages(self) -> None:
        evidence = build_evidence(eligible_snapshot(), policy())
        request_key = "e" * 64
        receipt = receipt_markdown(result_for(evidence), evidence, "submitted", "submitted", request_key)
        pages = [[], [{"body": receipt, "user": {"login": "fullsend-ai-coder[bot]"}}]]
        with mock.patch("auto_merge_finalize.gh", return_value=json.dumps(pages)) as request:
            self.assertEqual(existing_receipt_phases("fullsend-ai/auto-merge", 7, request_key), {"submitted"})
            self.assertIn("--paginate", request.call_args.args)

    def test_receipt_parser_rejects_embedded_marker(self) -> None:
        evidence = build_evidence(eligible_snapshot(), policy())
        receipt = receipt_markdown(result_for(evidence), evidence, "submitted", "submitted")
        self.assertEqual(parse_receipt_header(receipt)["phase"], "submitted")
        self.assertIsNone(parse_receipt_header("Earlier text\n\n" + receipt))


if __name__ == "__main__":
    unittest.main()
