#!/usr/bin/env python3
"""Tests that queue reauthorization checks Fullsend semantics, not SCM policy."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


SCRIPTS = Path(__file__).parents[1] / ".fullsend" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

from auto_merge_finalize import receipt_markdown  # noqa: E402
from auto_merge_gate import build_evidence  # noqa: E402
from auto_merge_queue_gate import evaluate_merge_group  # noqa: E402
from test_auto_merge import BASE, HEAD, QUEUE_HEAD, eligible_snapshot, human_comment, policy, result_for  # noqa: E402


def queue_event() -> dict:
    return {
        "action": "checks_requested",
        "repository": {"full_name": "fullsend-ai/auto-merge"},
        "merge_group": {
            "head_sha": QUEUE_HEAD,
            "base_sha": BASE,
            "head_ref": "refs/heads/gh-readonly-queue/main/pr-7-example",
        },
    }


def submitted_receipt(snapshot: dict | None = None) -> str:
    evidence = build_evidence(snapshot or eligible_snapshot(), policy(mode="lab-automatic"))
    return receipt_markdown(result_for(evidence), evidence, "submitted", "Submitted to GitHub SCM.")


def snapshot_with_receipt() -> dict:
    snapshot = eligible_snapshot()
    snapshot["comments"].append(
        {
            "id": 401,
            "body": submitted_receipt(),
            "created_at": "2026-09-23T20:02:00Z",
            "updated_at": "2026-09-23T20:02:00Z",
            "author_association": "NONE",
            "user": {"login": "fullsend-ai-coder[bot]", "type": "Bot"},
        }
    )
    return snapshot


class MergeQueueAuthorizationTests(unittest.TestCase):
    def evaluate(self, snapshot: dict | None = None, event: dict | None = None) -> dict:
        return evaluate_merge_group(event or queue_event(), snapshot or snapshot_with_receipt(), policy(mode="lab-automatic"))

    def test_matching_semantic_receipt_authorizes_queue_revision(self) -> None:
        result = self.evaluate()
        self.assertTrue(result["authorized"], result["failures"])
        self.assertFalse(result["scm_policy_checked"])

    def test_queue_gate_does_not_need_rulesets_or_check_runs(self) -> None:
        snapshot = snapshot_with_receipt()
        self.assertNotIn("rulesets", snapshot)
        self.assertNotIn("check_runs", snapshot)
        self.assertTrue(self.evaluate(snapshot)["authorized"])

    def test_human_authored_receipt_is_rejected(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["comments"][-1]["user"] = {"login": "ascerra", "type": "User"}
        self.assertFalse(self.evaluate(snapshot)["authorized"])

    def test_embedded_receipt_marker_is_rejected(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["comments"][-1]["body"] = "Earlier output\n\n" + snapshot["comments"][-1]["body"]
        self.assertFalse(self.evaluate(snapshot)["authorized"])

    def test_changed_head_or_base_is_rejected(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["pull_request"]["head"]["sha"] = "d" * 40
        self.assertFalse(self.evaluate(snapshot)["authorized"])
        event = queue_event()
        event["merge_group"]["base_sha"] = "e" * 40
        self.assertFalse(self.evaluate(event=event)["authorized"])

    def test_new_human_context_invalidates_prior_semantic_receipt(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["comments"].append(human_comment("Please pause; deployment sequencing is unresolved.", comment_id=402))
        self.assertFalse(self.evaluate(snapshot)["authorized"])

    def test_changed_risk_assessment_invalidates_prior_semantic_receipt(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["comments"][0]["body"] = snapshot["comments"][0]["body"].replace("low (1/5)", "high (4/5)")
        self.assertFalse(self.evaluate(snapshot)["authorized"])

    def test_fork_pull_request_is_rejected(self) -> None:
        snapshot = snapshot_with_receipt()
        snapshot["pull_request"]["head"]["repo"]["full_name"] = "outsider/auto-merge"
        self.assertFalse(self.evaluate(snapshot)["authorized"])


if __name__ == "__main__":
    unittest.main()
