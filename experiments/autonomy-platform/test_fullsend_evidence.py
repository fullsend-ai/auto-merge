import base64
import copy
import json
import unittest

import fullsend_evidence as f
import github_observe as g


def encode(data):
    return base64.b64encode(json.dumps(data).encode()).decode()


def fixture(data=None):
    data = data or {"version": 2, "action": "approve", "findings": []}
    user = {"id": f.BOT_ID, "login": f.BOT_LOGIN, "type": "Bot"}
    review = {
        "id": 1,
        "user": user,
        "commit_id": "a" * 40,
        "state": "APPROVED",
        "submitted_at": "2026-10-15T01:00:01Z",
    }
    comment = {
        "id": 2,
        "user": user,
        "updated_at": "2026-10-15T01:00:00Z",
        "body": f.SUMMARY
        + "\n<!-- fullsend:review-findings-v2:"
        + encode(data)
        + " -->\n<!-- **Head SHA:** "
        + "a" * 40
        + " -->\nSYNTHETIC_SECRET_SENTINEL",
    }
    return review, comment


class EvidenceTests(unittest.TestCase):
    def test_real_contract_clear_ledger_without_retaining_prose(self):
        r, c = fixture()
        result = f.findings("a" * 40, [r], [c])
        self.assertTrue(result["value"])
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(result))

    def test_missing_wrong_producer_stale_edit_and_wrong_head_hold(self):
        for field, value in [
            ("head", "b" * 40),
            ("producer", 999),
            ("time", "2026-10-15T01:00:02Z"),
            ("history", True),
        ]:
            r, c = fixture()
            head = "a" * 40
            if field == "head":
                head = value
            elif field == "producer":
                c["user"] = dict(c["user"], id=value)
            elif field == "time":
                c["updated_at"] = value
            else:
                c["body"] = f.SUMMARY + "\n<!-- sticky:history-start -->\n" + c["body"]
            self.assertIsNone(f.findings(head, [r], [c])["value"])
        self.assertIsNone(f.findings("a" * 40, None, None)["value"])

    def test_open_carried_findings_reject_and_comment_cannot_pass(self):
        row = {
            "id": "f_123",
            "severity": "info",
            "category": "stale-doc",
            "file": "docs/a.md",
        }
        for action in ["approve", "reject", "comment", "request-changes"]:
            data = {"version": 2, "action": action, "findings": [row]}
            r, c = fixture(data)
            self.assertFalse(f.findings("a" * 40, [r], [c])["value"])

    def test_closed_findings_and_reclassification(self):
        data = {
            "version": 2,
            "action": "approve",
            "findings": [
                {
                    "id": "f_123",
                    "severity": "low",
                    "category": "stale-doc",
                    "file": None,
                }
            ],
        }
        for state, expected in [
            ("resolved_by_change", True),
            ("dismissed_by_human", True),
            ("reclassified", False),
            ("open", False),
        ]:
            data["dispositions"] = [{"id": "f_123", "status": state}]
            self.assertEqual(f.ledger_clear(encode(data)), expected)
        data["dispositions"][0]["status"] = "dismissed_by_human"
        data["findings"][0]["severity"] = "high"
        with self.assertRaises(ValueError):
            f.ledger_clear(encode(data))

    def test_malformed_duplicate_version_and_orphan_disposition_hold(self):
        for mutate in [
            lambda d: d.update(version=3),
            lambda d: d.update(findings=[{}]),
            lambda d: d.update(
                dispositions=[{"id": "f_orphan", "status": "resolved_by_change"}]
            ),
        ]:
            d = {"version": 2, "action": "approve", "findings": []}
            mutate(d)
            r, c = fixture(d)
            self.assertIsNone(f.findings("a" * 40, [r], [c])["value"])
        r, c = fixture()
        c["body"] += "\n" + c["body"]
        self.assertIsNone(f.findings("a" * 40, [r], [c])["value"])
        duplicate = base64.b64encode(
            b'{"version":2,"version":2,"action":"approve","findings":[]}'
        ).decode()
        with self.assertRaises(ValueError):
            f.ledger_clear(duplicate)

    def test_newer_nonapproving_review_supersedes_old_approval(self):
        r, c = fixture()
        newer = dict(r, id=3, state="COMMENTED")
        self.assertFalse(f.findings("a" * 40, [r, newer], [c])["value"])

    def test_risk_comment_and_label_do_not_establish_revision_binding(self):
        _, c = fixture()
        c["body"] = "<!-- fullsend:risk-assessment -->\n**Risk Assessment: low (1/5)**"
        self.assertEqual(f.risk_gap([c]), "fullsend_risk_missing_revision_binding")


class QueueTests(unittest.TestCase):
    def setup_proof(self):
        sha = "d" * 40
        tree = {
            "tree": [
                {"path": p, "type": "blob", "sha": "c" * 40} for p in g.QUEUE_PATHS
            ]
        }
        rules = [
            {"type": "merge_queue"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {"context": n, "integration_id": 15368}
                        for n in g.CHECK_NAMES | {"Merge group proof"}
                    ]
                },
            },
        ]
        pull = {
            "merged": True,
            "merge_commit_sha": sha,
            "base": {"ref": "main", "repo": {"full_name": g.REPOSITORY}},
        }
        run = {
            "id": g.QUEUE_PROOF_RUN,
            "workflow_id": 365189945,
            "event": "merge_group",
            "path": ".github/workflows/ci.yml",
            "status": "completed",
            "conclusion": "success",
            "head_sha": sha,
            "head_branch": "gh-readonly-queue/main/pr-27-abc",
            "repository": {"full_name": g.REPOSITORY},
            "head_repository": {"full_name": g.REPOSITORY},
        }

        class Client:
            def get(self, path):
                if "pulls/" in path:
                    return pull
                if "actions/" in path:
                    return run
                return tree

        return Client(), rules, tree, run

    def test_historical_route_proof_is_bound_to_current_sources(self):
        client, rules, tree, run = self.setup_proof()
        self.assertTrue(
            g.queue_proof(client, "repos/" + g.REPOSITORY + "/", rules, tree)["value"]
        )
        changed = copy.deepcopy(tree)
        changed["tree"][0]["sha"] = "f" * 40
        self.assertIsNone(g.queue_proof(client, "", rules, changed)["value"])
        for field, value in [
            ("event", "pull_request"),
            ("conclusion", "failure"),
            ("head_sha", "a" * 40),
        ]:
            before = run[field]
            run[field] = value
            self.assertFalse(g.queue_proof(client, "", rules, tree)["value"])
            run[field] = before
        self.assertFalse(g.queue_proof(client, "", [], tree)["value"])


class RiskReceiptTests(unittest.TestCase):
    def receipt(self, **changes):
        data = {
            "version": 1,
            "head_sha": "a" * 40,
            "score": 1,
            "level": "low",
            "config_sha": "b" * 40,
            "run_id": 1234,
            "run_attempt": 1,
        }
        data.update(changes)
        review, comment = fixture()
        comment["body"] = (
            "<!-- fullsend:review-risk-v1:" + encode(data) + " -->\n" + comment["body"]
        )
        return data, review, comment

    def test_valid_risk_requires_completed_trusted_producer(self):
        data, review, comment = self.receipt()
        self.assertEqual(
            f.risk("a" * 40, [review], [comment], lambda d: d == data)["value"], 1
        )
        self.assertIsNone(
            f.risk("a" * 40, [review], [comment], lambda d: False)["value"]
        )

    def test_malformed_unbound_degraded_and_inconsistent_risk_are_unknown(self):
        for changes in [
            {"score": True},
            {"score": 0},
            {"score": 6},
            {"level": "critical"},
            {"head_sha": "f" * 40},
            {"config_sha": "bad"},
            {"run_id": "1234"},
            {"run_attempt": 0},
            {"degraded": "missing-context"},
            {"version": 2},
        ]:
            _, review, comment = self.receipt(**changes)

            def never(data):
                self.fail("Unvalidated data reached the producer lookup")

            self.assertIsNone(f.risk("a" * 40, [review], [comment], never)["value"])

    def test_producer_is_bound_to_run_attempt_event_and_current_configuration(self):
        receipt, _, _ = self.receipt()
        tree = {
            "tree": [
                {"path": p, "type": "blob", "sha": "c" * 40}
                for p in g.RISK_SOURCE_PATHS
            ]
        }
        run = {
            "id": 1234,
            "run_attempt": 1,
            "workflow_id": 365189947,
            "path": ".github/workflows/fullsend.yaml",
            "event": "issue_comment",
            "head_branch": "main",
            "head_sha": "b" * 40,
            "status": "completed",
            "conclusion": "success",
            "repository": {"full_name": g.REPOSITORY},
            "head_repository": {"full_name": g.REPOSITORY},
        }

        class Client:
            def get(self, path):
                return tree if "git/trees" in path else run

        client = Client()
        self.assertTrue(g.risk_producer(client, "", tree, receipt))
        for key, value in [
            ("event", "pull_request"),
            ("run_attempt", 2),
            ("head_branch", "untrusted"),
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("workflow_id", 99),
        ]:
            old = run[key]
            run[key] = value
            self.assertFalse(g.risk_producer(client, "", tree, receipt))
            run[key] = old
        changed = copy.deepcopy(tree)
        changed["tree"][0]["sha"] = "f" * 40
        self.assertFalse(g.risk_producer(client, "", changed, receipt))

    def test_host_refuses_unpinned_source_before_execution(self):
        import importlib.util
        from pathlib import Path
        from unittest import mock

        path = (
            Path(__file__).resolve().parents[2]
            / ".fullsend/scripts/post-review-gemara.py"
        )
        spec = importlib.util.spec_from_file_location("receipt_host", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                module.prepare(Path("/unused"), b"untrusted", b"untrusted")
            run.assert_not_called()
