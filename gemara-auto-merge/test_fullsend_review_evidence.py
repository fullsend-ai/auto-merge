import base64
import copy
import json
import unittest

import fullsend_review_evidence as f
import github_pr_evidence as g


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

    def producer_fixture(self):
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
            "check_suite_id": 4321,
            "referenced_workflows": [dict(g.RISK_DISPATCH)],
        }
        suite = {
            "id": 4321,
            "app": {"id": 15368},
            "head_sha": "a" * 40,
            "head_branch": "feature",
            "pull_requests": [
                {
                    "number": 26,
                    "head": {
                        "ref": "feature",
                        "sha": "a" * 40,
                        "repo": {"id": g.REPOSITORY_ID},
                    },
                    "base": {
                        "ref": "main",
                        "sha": "b" * 40,
                        "repo": {"id": g.REPOSITORY_ID},
                    },
                }
            ],
        }

        class Client:
            def get(self, path):
                if "check-suites/" in path:
                    return suite
                return tree if "git/trees" in path else run

        client = Client()
        from unittest import mock

        patcher = mock.patch.object(
            g,
            "local_risk_blobs",
            return_value={r["path"]: r["sha"] for r in tree["tree"]},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return receipt, tree, run, client

    def test_producer_is_bound_to_run_attempt_event_and_current_configuration(self):
        receipt, tree, run, client = self.producer_fixture()
        self.assertTrue(g.risk_producer(client, "", tree, receipt))
        self.assertTrue(
            g.risk_producer(client, "", tree, receipt, {"head": {"sha": "a" * 40}})
        )
        for key, value in [
            ("event", "pull_request"),
            ("run_attempt", 2),
            ("head_branch", "untrusted"),
            ("head_sha", "f" * 40),
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

    def test_automatic_review_binds_pr_head_and_base_configuration_separately(self):
        receipt, tree, run, client = self.producer_fixture()
        run.update(
            event="pull_request_target", head_branch="feature", head_sha="a" * 40
        )
        pr = {
            "number": 26,
            "head": {
                "sha": "a" * 40,
                "ref": "feature",
                "repo": {"full_name": g.REPOSITORY},
            },
            "base": {
                "sha": "b" * 40,
                "ref": "main",
                "repo": {"full_name": g.REPOSITORY},
            },
        }
        self.assertTrue(g.risk_producer(client, "", tree, receipt, pr, "b" * 40))
        self.assertFalse(g.risk_producer(client, "", tree, receipt))
        for side, field, value in [
            ("head", "sha", "f" * 40),
            ("head", "ref", "other"),
            ("head", "repo", {"full_name": "someone/fork"}),
            ("base", "sha", "f" * 40),
            ("base", "ref", "other"),
            ("base", "repo", {"full_name": "someone/other"}),
        ]:
            changed = copy.deepcopy(pr)
            changed[side][field] = value
            with self.subTest(side=side, field=field):
                self.assertFalse(
                    g.risk_producer(client, "", tree, receipt, changed, "b" * 40)
                )
        for field, value in [
            ("event", "pull_request"),
            ("head_sha", "f" * 40),
            ("head_branch", "other"),
            ("run_attempt", 2),
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("workflow_id", 99),
            ("path", ".github/workflows/other.yaml"),
            ("head_repository", {"full_name": "someone/fork"}),
            ("repository", {"full_name": "someone/other"}),
            ("check_suite_id", 99),
            ("referenced_workflows", []),
            ("referenced_workflows", [dict(g.RISK_DISPATCH, sha="f" * 40)]),
        ]:
            original = run[field]
            run[field] = value
            with self.subTest(field=field):
                self.assertFalse(
                    g.risk_producer(client, "", tree, receipt, pr, "b" * 40)
                )
            run[field] = original
        changed = copy.deepcopy(tree)
        changed["tree"][0]["sha"] = "f" * 40
        self.assertFalse(g.risk_producer(client, "", changed, receipt, pr, "b" * 40))
        for head_tree in [None, {"tree": []}, dict(tree, truncated=True), changed]:

            class ChangedHeadClient:
                def get(self, path):
                    if f"git/trees/{receipt['head_sha']}?" in path:
                        return head_tree
                    return client.get(path)

            with self.subTest(head_tree=head_tree):
                self.assertFalse(
                    g.risk_producer(
                        ChangedHeadClient(), "", tree, receipt, pr, "b" * 40
                    )
                )
        suite = client.get("check-suites/4321")
        changed_suites = [
            None,
            {},
            dict(suite, pull_requests=[]),
            dict(suite, pull_requests=suite["pull_requests"] * 2),
            dict(suite, app={"id": 999}),
            dict(suite, head_sha="f" * 40),
            dict(suite, head_branch="other"),
        ]
        for side, field, value in [
            ("base", "ref", "non-main"),
            ("base", "sha", "f" * 40),
            ("base", "repo", {"id": 999}),
            ("head", "sha", "f" * 40),
            ("head", "ref", "other"),
            ("head", "repo", {"id": 999}),
        ]:
            changed = copy.deepcopy(suite)
            changed["pull_requests"][0][side][field] = value
            changed_suites.append(changed)
        changed = copy.deepcopy(suite)
        changed["pull_requests"][0]["number"] = 99
        changed_suites.append(changed)
        for changed_suite in changed_suites:

            class ChangedSuiteClient:
                def get(self, path):
                    return (
                        changed_suite if "check-suites/" in path else client.get(path)
                    )

            with self.subTest(suite=changed_suite):
                self.assertFalse(
                    g.risk_producer(
                        ChangedSuiteClient(), "", tree, receipt, pr, "b" * 40
                    )
                )

        class MovingSuiteClient:
            reads = 0

            def get(self, path):
                if "check-suites/" in path:
                    self.reads += 1
                    return (
                        suite if self.reads == 1 else dict(suite, head_branch="other")
                    )
                return client.get(path)

        self.assertFalse(
            g.risk_producer(MovingSuiteClient(), "", tree, receipt, pr, "b" * 40)
        )

    def test_automatic_producer_changes_during_collection_hold(self):
        receipt, tree, run, client = self.producer_fixture()
        run.update(
            event="pull_request_target", head_branch="feature", head_sha="a" * 40
        )
        pr = {
            "number": 26,
            "head": {
                "sha": "a" * 40,
                "ref": "feature",
                "repo": {"full_name": g.REPOSITORY},
            },
            "base": {
                "sha": "b" * 40,
                "ref": "main",
                "repo": {"full_name": g.REPOSITORY},
            },
        }

        class ChangingClient:
            reads = 0

            def get(self, path):
                if "check-suites/" in path:
                    return client.get(path)
                if "git/trees" in path:
                    return tree
                self.reads += 1
                return dict(run, run_attempt=self.reads)

        self.assertFalse(
            g.risk_producer(ChangingClient(), "", tree, receipt, pr, "b" * 40)
        )

    def test_producer_checks_history_against_observed_main_tip(self):
        receipt, tree, run, client = self.producer_fixture()
        run.update(
            event="pull_request_target", head_branch="feature", head_sha="a" * 40
        )
        pr = {
            "number": 26,
            "head": {
                "sha": "a" * 40,
                "ref": "feature",
                "repo": {"full_name": g.REPOSITORY},
            },
            "base": {
                "sha": "b" * 40,
                "ref": "main",
                "repo": {"full_name": g.REPOSITORY},
            },
        }
        main = "e" * 40
        comparison = {
            "status": "ahead",
            "base_commit": {"sha": "b" * 40},
            "merge_base_commit": {"sha": "b" * 40},
            "total_commits": 1,
            "commits": [{"sha": main}],
        }
        commit = {"sha": main, "files": [{"filename": "docs/example-feature.md"}]}

        class HistoryClient:
            def get(self, path):
                if "compare/" in path:
                    self_test.assertIn("b" * 40 + "..." + main, path)
                    return comparison
                if "commits/" in path:
                    return commit
                return client.get(path)

        self_test = self
        history = HistoryClient()
        self.assertTrue(g.risk_producer(history, "", tree, receipt, pr, main))
        commit["files"] = [{"filename": next(iter(g.RISK_SOURCE_PATHS))}]
        self.assertFalse(g.risk_producer(history, "", tree, receipt, pr, main))
        self.assertFalse(g.risk_producer(history, "", tree, receipt, pr, None))

    def test_dispatcher_pin_matches_managed_workflow(self):
        from pathlib import Path
        import re

        workflow = (
            Path(__file__).resolve().parents[1] / ".github/workflows/fullsend.yaml"
        )
        if (workflow.parents[2] / ".fullsend/vendor-manifest.yaml").exists():
            self.assertEqual(
                re.findall(
                    r"^    uses: (fullsend-ai/fullsend/\.github/workflows/reusable-dispatch\.yml@\S+)$",
                    workflow.read_text(),
                    re.M,
                ),
                ["fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@1528aac1b8361ef7f5cad1ba55f304402761580c"],
            )
            self.assertTrue((workflow.parents[2] / ".defaults/action.yml").is_file())
            return
        uses = re.findall(
            r"^    uses: (fullsend-ai/fullsend/\.github/workflows/reusable-dispatch\.yml@\S+)$",
            workflow.read_text(),
            re.M,
        )
        self.assertEqual(uses, [g.RISK_DISPATCH["path"]])
        self.assertEqual(uses[0].rsplit("@", 1)[1], g.RISK_DISPATCH["sha"])

    def test_host_history_checks_each_commit_including_a_revert(self):
        configuration, first, main = "b" * 40, "d" * 40, "e" * 40
        comparison = {
            "status": "ahead",
            "base_commit": {"sha": configuration},
            "merge_base_commit": {"sha": configuration},
            "total_commits": 2,
            "commits": [{"sha": first}, {"sha": main}],
        }
        rows = {
            first: {"sha": first, "files": [{"filename": "docs/one.md"}]},
            main: {"sha": main, "files": [{"filename": "docs/two.md"}]},
        }

        class Client:
            def get(self, path):
                if "compare/" in path:
                    return comparison
                return rows.get(path.split("commits/")[1].split("?")[0])

        client = Client()
        self.assertTrue(g.risk_host_history(client, "", configuration, main))
        source = next(iter(g.RISK_SOURCE_PATHS))
        # A clean final tree cannot conceal an intermediate host-source change.
        rows[first]["files"] = [{"filename": source}]
        rows[main]["files"] = [{"filename": source}]
        self.assertFalse(g.risk_host_history(client, "", configuration, main))
        rows[main]["files"] = [{"filename": "docs/two.md"}]
        rows[first]["files"] = [{"filename": "elsewhere", "previous_filename": source}]
        self.assertFalse(g.risk_host_history(client, "", configuration, main))
        rows[first]["files"] = [{"filename": "docs/one.md"}]
        rows[main]["files"] = [{"filename": "docs/two.md"}]
        for changes in [
            {"status": "diverged"},
            {"merge_base_commit": {"sha": "f" * 40}},
            {"total_commits": 21},
            {"commits": [{"sha": main}]},
            {"commits": [{"sha": main}, {"sha": main}]},
        ]:
            old = copy.deepcopy(comparison)
            comparison.update(changes)
            with self.subTest(changes=changes):
                self.assertFalse(g.risk_host_history(client, "", configuration, main))
            comparison.clear()
            comparison.update(old)
        for files in [None, [{}], [{"filename": "docs/a.md"}] * 100]:
            rows[main]["files"] = files
            self.assertFalse(g.risk_host_history(client, "", configuration, main))
        rows[main] = None
        self.assertFalse(g.risk_host_history(client, "", configuration, main))
        self.assertFalse(g.risk_host_history(client, "", configuration, None))
        self.assertTrue(g.risk_host_history(client, "", configuration, configuration))

    def test_host_refuses_unpinned_source_before_execution(self):
        import importlib.util
        from pathlib import Path
        from unittest import mock

        path = (
            Path(__file__).resolve().parents[1]
            / ".fullsend/scripts/post-review-gemara.py"
        )
        spec = importlib.util.spec_from_file_location("receipt_host", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                module.prepare(Path("/unused"), b"untrusted", b"untrusted")
            run.assert_not_called()
