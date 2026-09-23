#!/usr/bin/env python3
"""Adversarial tests for merge-queue revision authorization."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


SCRIPTS = Path(__file__).parents[1] / ".fullsend" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

from auto_merge_finalize import idempotency_key, receipt_markdown  # noqa: E402
from auto_merge_gate import build_evidence  # noqa: E402
from auto_merge_queue_gate import evaluate_merge_group  # noqa: E402
from test_auto_merge import BASE, HEAD, eligible_snapshot, policy  # noqa: E402


QUEUE_HEAD = "d" * 40


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


def queued_receipt() -> str:
    evidence = build_evidence(eligible_snapshot(), policy())
    result = {
        "decision": "APPROVE",
        "binding": evidence["binding"],
        "summary": "The bounded change is approved",
        "reasons": ["All policy gates passed"],
        "risk_signals": [],
    }
    request_key = idempotency_key(evidence["binding"], "queue")
    return receipt_markdown(result, evidence, "queued", "GitHub accepted queue enrollment.", request_key)


def pull_request() -> dict:
    return {
        "number": 7,
        "state": "open",
        "draft": False,
        "head": {"sha": HEAD, "repo": {"full_name": "fullsend-ai/auto-merge"}},
        "base": {"ref": "main"},
        "labels": [{"name": "risk/low"}],
    }


def rulesets() -> list[dict]:
    return [{"enforcement": "active", "rules": [{"type": "merge_queue"}]}]


def evaluate(comments: list[dict], **overrides: object) -> dict:
    inputs = {
        "event": queue_event(),
        "pull_request": pull_request(),
        "comments": comments,
        "rulesets": rulesets(),
        "repository": "fullsend-ai/auto-merge",
        "allowed_risk_levels": {"low", "moderate"},
    }
    inputs.update(overrides)
    return evaluate_merge_group(**inputs)


class MergeQueueAuthorizationTests(unittest.TestCase):
    def test_canonical_machine_receipt_authorizes_queue_revision(self) -> None:
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        result = evaluate(comments)
        self.assertTrue(result["authorized"], result["failures"])

    def test_human_authored_receipt_is_rejected(self) -> None:
        comments = [{"body": queued_receipt(), "user": {"login": "ascerra"}}]
        self.assertFalse(evaluate(comments)["authorized"])

    def test_marker_embedded_in_trusted_comment_is_rejected(self) -> None:
        comments = [
            {
                "body": "Earlier bot output that must not count.\n\n" + queued_receipt(),
                "user": {"login": "fullsend-ai-coder[bot]"},
            }
        ]
        self.assertFalse(evaluate(comments)["authorized"])

    def test_self_consistent_but_unbound_request_key_is_rejected(self) -> None:
        forged_key = "f" * 64
        receipt = queued_receipt()
        marker_key = receipt.split(":", 3)[2]
        forged = receipt.replace(marker_key, forged_key)
        comments = [{"body": forged, "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments)["authorized"])

    def test_receipt_for_different_base_is_rejected(self) -> None:
        event = queue_event()
        event["merge_group"]["base_sha"] = "f" * 40
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments, event=event)["authorized"])

    def test_receipt_for_different_head_is_rejected(self) -> None:
        pr = pull_request()
        pr["head"]["sha"] = "f" * 40
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments, pull_request=pr)["authorized"])

    def test_fork_pull_request_is_rejected(self) -> None:
        pr = pull_request()
        pr["head"]["repo"]["full_name"] = "outsider/auto-merge"
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments, pull_request=pr)["authorized"])

    def test_missing_active_queue_rule_is_rejected(self) -> None:
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments, rulesets=[])["authorized"])

    def test_disallowed_risk_is_rejected(self) -> None:
        pr = pull_request()
        pr["labels"] = [{"name": "risk/high"}]
        comments = [{"body": queued_receipt(), "user": {"login": "fullsend-ai-coder[bot]"}}]
        self.assertFalse(evaluate(comments, pull_request=pr)["authorized"])


if __name__ == "__main__":
    unittest.main()
