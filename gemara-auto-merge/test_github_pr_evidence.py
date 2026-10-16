import copy
import unittest
from unittest import mock

import github_pr_evidence as g


def pr():
    return {
        "head": {"sha": "a" * 40},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": g.REPOSITORY}},
        "state": "open",
        "draft": False,
    }


class FixtureClient:
    def __init__(self, changed=False, closed=False):
        self.errors = set()
        self.calls = 0
        self.changed = changed
        self.closed = closed

    def get(self, path):
        if path.endswith("pulls/26"):
            self.calls += 1
            result = pr()
            if self.changed and self.calls > 1:
                result["head"]["sha"] = "f" * 40
            if self.closed:
                result["state"] = "closed"
            return result
        if path.endswith("/branches/main") and "/rules/" not in path:
            return {"commit": {"sha": "b" * 40}}
        if "rules/branches" in path:
            return [{"type": "pull_request"}]
        if "git/trees" in path:
            return {"tree": [{"path": ".fullsend/config.yaml", "sha": "c" * 40}]}
        raise AssertionError("unexpected endpoint")

    def pages(self, path, key=None):
        if "/comments" in path:
            return []
        if "reviews" in path:
            return [
                {
                    "id": 1,
                    "user": {
                        "id": 278716355,
                        "login": "fullsend-ai-review[bot]",
                        "type": "Bot",
                    },
                    "commit_id": "a" * 40,
                    "state": "APPROVED",
                    "body": "SYNTHETIC_SECRET_SENTINEL",
                }
            ]
        if "files" in path:
            return [
                {
                    "filename": "docs/example-feature.md",
                    "patch": "SYNTHETIC_SECRET_SENTINEL",
                }
            ]
        return [
            {
                "name": name,
                "head_sha": "a" * 40,
                "app": {"id": 15368},
                "status": "completed",
                "conclusion": "success",
                "output": {"text": "SYNTHETIC_SECRET_SENTINEL"},
            }
            for name in g.CHECK_NAMES
        ]


class ObserverTests(unittest.TestCase):
    def test_observer_passes_fetched_pr_to_risk_producer(self):
        class AdvancedMainClient(FixtureClient):
            def get(self, path):
                if path.endswith("/branches/main") and "/rules/" not in path:
                    return {"commit": {"sha": "e" * 40}}
                return super().get(path)

        client = AdvancedMainClient()
        receipt = {"head_sha": "a" * 40, "config_sha": "b" * 40}

        def verify_risk(head, reviews, comments, verify_producer):
            verify_producer(receipt)
            return {"value": None, "reason": "fixture_unverified"}

        with (
            mock.patch.object(g, "risk", side_effect=verify_risk),
            mock.patch.object(g, "risk_producer", return_value=False) as producer,
        ):
            g.observe(26, client)
        producer.assert_called_once_with(
            client,
            "repos/" + g.REPOSITORY + "/",
            {"tree": [{"path": ".fullsend/config.yaml", "sha": "c" * 40}]},
            receipt,
            pr(),
            "e" * 40,
        )

    def test_api_payload_text_is_never_in_retained_report(self):
        import json

        result = g.observe(26, FixtureClient())
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(result))
        self.assertTrue(result["fullsend_review_metadata_present"])
        self.assertEqual(result["shadow"]["decision"], "hold")
        self.assertFalse(result["mutation_permitted"])
        findings = next(
            row
            for row in result["shadow"]["evaluation"]["assessments"]
            if row["id"] == "AM-FINDINGS"
        )
        self.assertEqual(
            (findings["state"], findings["reason"]), ("unknown", "missing")
        )

    def test_summary_explains_holds_without_raw_api_text(self):
        report = g.observe(26, FixtureClient())
        text = g.summary(report)
        self.assertIn("no merge authority", text)
        self.assertIn("Repository readiness", text)
        self.assertIn("PR candidate", text)
        self.assertIn("Gemara: hold", text)
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", text)
        self.assertIn("Policy assessment plans", text)

    def test_cli_surfaces_safe_unsupported_policy_code(self):
        import contextlib
        import io
        import json

        with (
            mock.patch("sys.argv", ["github_pr_evidence.py", "--pr", "28"]),
            mock.patch.object(
                g,
                "observe",
                side_effect=g.InputError("gemara_unsupported_policy_semantics"),
            ),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(g.main(), 2)
        self.assertEqual(
            json.loads(output.getvalue())["error"],
            "gemara_unsupported_policy_semantics",
        )

    def test_changed_candidate_and_closed_pr_cannot_pass(self):
        for client in [FixtureClient(changed=True), FixtureClient(closed=True)]:
            result = g.observe(26, client)
            self.assertEqual(result["shadow"]["decision"], "hold")
            self.assertIn("candidate_not_current_open_pr", result["shadow"]["reasons"])

    def test_actual_target_branch_is_independent_of_pr_base_snapshot(self):
        class OlderSnapshot(FixtureClient):
            def get(self, path):
                result = super().get(path)
                if "pulls/26" in path:
                    result["base"]["sha"] = "d" * 40
                return result

        report = g.observe(26, OlderSnapshot())
        self.assertEqual(report["base_sha"], "b" * 40)
        self.assertEqual(report["github_pr_base_snapshot_sha"], "d" * 40)
        self.assertTrue(report["stable_during_collection"])

    def test_target_branch_advance_during_collection_holds(self):
        class MovingBranch(FixtureClient):
            def __init__(self):
                super().__init__()
                self.branches = 0

            def get(self, path):
                if path.endswith("/branches/main") and "/rules/" not in path:
                    self.branches += 1
                    return {
                        "commit": {"sha": ("b" if self.branches == 1 else "f") * 40}
                    }
                return super().get(path)

        report = g.observe(26, MovingBranch())
        self.assertFalse(report["stable_during_collection"])
        self.assertEqual(report["shadow"]["decision"], "hold")

    def test_reviews_comments_and_ci_must_stay_stable(self):
        for endpoint in ["/reviews", "/comments", "/check-runs"]:

            class ChangingClient(FixtureClient):
                def __init__(self):
                    super().__init__()
                    self.seen = 0

                def pages(self, path, key=None):
                    result = super().pages(path, key)
                    if endpoint in path:
                        self.seen += 1
                        if self.seen > 1:
                            return result + [{"id": 999}]
                    return result

            result = g.observe(26, ChangingClient())
            self.assertFalse(result["stable_during_collection"])
            self.assertEqual(result["shadow"]["decision"], "hold")

    def test_current_revision_and_latest_decisive_review_required(self):
        review = {
            "id": 1,
            "user": {
                "id": 278716355,
                "login": "fullsend-ai-review[bot]",
                "type": "Bot",
            },
            "commit_id": "a" * 40,
            "state": "APPROVED",
        }
        values, _ = g.normalize(pr(), [], [review], [])
        self.assertTrue(values["AM-REVIEW"])
        changed = copy.deepcopy(review)
        changed["id"] = 2
        changed["state"] = "CHANGES_REQUESTED"
        values, _ = g.normalize(pr(), [], [review, changed], [])
        self.assertFalse(values["AM-REVIEW"])
        review["commit_id"] = "b" * 40
        values, _ = g.normalize(pr(), [], [review], [])
        self.assertFalse(values["AM-REVIEW"])

    def test_check_names_without_expected_producer_do_not_pass(self):
        checks = [
            {
                "name": n,
                "head_sha": "a" * 40,
                "app": {"id": 999},
                "status": "completed",
                "conclusion": "success",
            }
            for n in g.CHECK_NAMES
        ]
        self.assertIsNone(g.normalize(pr(), checks, [], [])[0]["AM-CI"])
        for row in checks:
            row["app"]["id"] = 15368
        self.assertTrue(g.normalize(pr(), checks, [], [])[0]["AM-CI"])
        self.assertIsNone(g.normalize(pr(), checks + checks, [], [])[0]["AM-CI"])

    def test_pending_ci_is_unknown_but_a_completed_failure_is_false(self):
        checks = [
            {
                "name": n,
                "head_sha": "a" * 40,
                "app": {"id": 15368},
                "status": "in_progress",
                "conclusion": None,
            }
            for n in g.CHECK_NAMES
        ]
        self.assertIsNone(g.normalize(pr(), checks, [], [])[0]["AM-CI"])
        checks[0].update(status="completed", conclusion="failure")
        self.assertFalse(g.normalize(pr(), checks, [], [])[0]["AM-CI"])
        checks[0]["conclusion"] = "success"
        self.assertIsNone(g.normalize(pr(), checks, [], [])[0]["AM-CI"])
        checks[1].update(status="completed", conclusion="success")
        self.assertTrue(g.normalize(pr(), checks, [], [])[0]["AM-CI"])

    def test_protected_policy_change_not_classified_as_harmless_docs(self):
        for path in (
            ".fullsend/config.yaml",
            "gemara-auto-merge/config/documentation-auto-merge-settings.json",
            "gemara-auto-merge/catalogs/documentation-auto-merge-controls.json",
            "gemara-auto-merge/policies/documentation-auto-merge-policy.json",
            "gemara-auto-merge/authorize_auto_merge.py",
            "experiments/legacy-policy.json",
        ):
            with self.subTest(path=path):
                values, _ = g.normalize(pr(), [], [], [{"filename": path}])
                self.assertFalse(values["AM-PROTECTED"])
                self.assertIsNone(values["AM-CLASS"])

    def test_renames_and_nested_governance_cannot_look_unprotected(self):
        for previous in (
            ".github/workflows/ci.yml",
            ".fullsend/config.yaml",
            "experiments/legacy.json",
            "gemara-auto-merge/policy_evaluation.py",
            "scripts/validate_example.py",
            "AGENTS.md",
            "docs/AGENTS.md",
            "CODEOWNERS",
            "docs/CODEOWNERS",
        ):
            with self.subTest(previous=previous):
                values, _ = g.normalize(
                    pr(),
                    [],
                    [],
                    [
                        {
                            "filename": "docs/example-feature.md",
                            "previous_filename": previous,
                            "status": "renamed",
                        }
                    ],
                )
                self.assertFalse(values["AM-PROTECTED"])
        for filename in ("docs/AGENTS.md", "docs/CODEOWNERS", "nested/AGENTS.md"):
            with self.subTest(filename=filename):
                values, _ = g.normalize(pr(), [], [], [{"filename": filename}])
                self.assertFalse(values["AM-PROTECTED"])
        for missing in (None, "", 123):
            with self.subTest(missing=missing):
                values, _ = g.normalize(
                    pr(),
                    [],
                    [],
                    [
                        {
                            "filename": "docs/example-feature.md",
                            "previous_filename": missing,
                        }
                    ],
                )
                self.assertFalse(values["AM-PROTECTED"])

    def test_ordinary_paths_remain_unprotected(self):
        for changed in (
            {"filename": "docs/example-feature.md"},
            {
                "filename": "docs/example-feature.md",
                "previous_filename": "docs/old.md",
                "status": "renamed",
            },
            {"filename": "docs/AGENTS-guide.md"},
            {"filename": "docs/CODEOWNERS-notes.md"},
        ):
            with self.subTest(changed=changed):
                values, _ = g.normalize(pr(), [], [], [changed])
                self.assertTrue(values["AM-PROTECTED"])

    def test_pagination_failure_discards_partial_results(self):
        client = g.Client()
        with mock.patch.object(client, "get", side_effect=[[{}] * 100, None]):
            self.assertIsNone(
                client.pages("repos/" + g.REPOSITORY + "/pulls/26/reviews")
            )
        with mock.patch.object(client, "get", return_value=[{}] * 100):
            self.assertIsNone(
                client.pages("repos/" + g.REPOSITORY + "/pulls/26/reviews")
            )
            self.assertIn("github_pagination_incomplete", client.errors)

    def test_no_cross_host_or_write_endpoint_is_accepted(self):
        client = g.Client()
        for path in [
            "https://example.invalid/",
            "repos/other/repo/pulls/1",
            "repos/" + g.REPOSITORY + "/../secrets",
        ]:
            with self.assertRaises(g.InputError):
                client.get(path)

    def test_comparison_allows_only_fixed_sha_pair_and_bounded_page(self):
        client = g.Client()
        endpoint = (
            "repos/"
            + g.REPOSITORY
            + "/compare/"
            + "b" * 40
            + "..."
            + "e" * 40
            + "?per_page=20"
        )
        with mock.patch.object(client.opener, "open") as request:
            request.return_value.__enter__.return_value.read.return_value = b"{}"
            self.assertEqual(client.get(endpoint), {})
            self.assertEqual(
                request.call_args.args[0].full_url, "https://api.github.com/" + endpoint
            )
            for changed in [
                endpoint.replace("per_page=20", "per_page=100"),
                endpoint.replace("b" * 40, "../main"),
                endpoint.replace("e" * 40, "main"),
            ]:
                with self.assertRaises(g.InputError):
                    client.get(changed)
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
