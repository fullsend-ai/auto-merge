import base64
import copy
import json
import unittest
from unittest import mock

import resolve_pr_from_event as r
from fullsend_review_evidence import BOT_ID, BOT_LOGIN


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.pr = {
            "state": "open",
            "draft": False,
            "head": {"sha": "a" * 40, "repo": {"full_name": r.g.REPOSITORY}},
            "base": {"ref": "main", "repo": {"full_name": r.g.REPOSITORY}},
        }
        self.client = mock.Mock()
        self.client.get.return_value = self.pr

    def test_manual_dispatch_binds_exact_head_and_rejects_foreign_forks(self):
        event = {"inputs": {"pr": "32", "head": "a" * 40}}
        self.assertEqual(
            r.resolve("workflow_dispatch", event, self.client),
            {"pr": 32, "head": "a" * 40},
        )
        for head in ["b" * 40, "bad"]:
            self.assertIsNone(
                r.resolve(
                    "workflow_dispatch",
                    {"inputs": {"pr": "32", "head": head}},
                    self.client,
                )
            )
        foreign = copy.deepcopy(self.pr)
        foreign["head"]["repo"]["full_name"] = "other/repo"
        self.client.get.return_value = foreign
        self.assertIsNone(r.resolve("workflow_dispatch", event, self.client))

    def test_ci_completion_resolves_but_merge_group_cannot_retrigger_writer(self):
        run = {
            "name": "CI",
            "event": "pull_request",
            "repository": {"full_name": r.g.REPOSITORY},
            "pull_requests": [{"number": 32}],
        }
        self.assertEqual(
            r.resolve("workflow_run", {"workflow_run": run}, self.client),
            {"pr": 32, "head": "a" * 40},
        )
        self.assertIsNone(
            r.resolve(
                "workflow_run",
                {"workflow_run": dict(run, event="merge_group")},
                self.client,
            )
        )
        self.assertIsNone(
            r.resolve(
                "workflow_run",
                {
                    "workflow_run": dict(
                        run, pull_requests=[{"number": 32}, {"number": 33}]
                    )
                },
                self.client,
            )
        )

    def test_receipt_is_only_a_run_bound_routing_hint_from_the_pinned_producer(self):
        marker = base64.b64encode(json.dumps({"run_id": 55}).encode()).decode()
        row = {
            "user": {"id": BOT_ID, "login": BOT_LOGIN, "type": "Bot"},
            "body": f"<!-- fullsend:review-risk-v1:{marker} -->",
            "issue_url": "https://api.github.com/repos/fullsend-ai/auto-merge/issues/32",
        }
        self.assertEqual(r.receipt_hint(row, 55), 32)
        self.assertIsNone(r.receipt_hint(row, 56))
        self.assertIsNone(
            r.receipt_hint(
                dict(row, user={"id": 1, "login": BOT_LOGIN, "type": "Bot"}), 55
            )
        )
        self.assertIsNone(
            r.receipt_hint(
                dict(
                    row, issue_url="https://api.github.com/repos/other/repo/issues/32"
                ),
                55,
            )
        )
        run = {
            "id": 55,
            "name": "fullsend",
            "event": "issue_comment",
            "repository": {"full_name": r.g.REPOSITORY},
            "pull_requests": [],
            "created_at": "2026-10-15T15:00:00Z",
        }
        self.client.get.side_effect = (
            lambda endpoint: [row] if "/issues/comments?" in endpoint else self.pr
        )
        self.assertEqual(
            r.resolve("workflow_run", {"workflow_run": run}, self.client),
            {"pr": 32, "head": "a" * 40},
        )
        self.client.get.side_effect = (
            lambda endpoint: [row] * 100 if "/issues/comments?" in endpoint else self.pr
        )
        self.assertIsNone(r.resolve("workflow_run", {"workflow_run": run}, self.client))
