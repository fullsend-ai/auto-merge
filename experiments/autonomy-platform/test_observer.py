import copy
import unittest
from unittest import mock

import github_observe as g


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
        if "rules/branches" in path:
            return [{"type": "pull_request"}]
        if "git/trees" in path:
            return {"tree": [{"path": ".fullsend/config.yaml", "sha": "c" * 40}]}
        raise AssertionError("unexpected endpoint")

    def pages(self, path, key=None):
        if "reviews" in path:
            return [
                {
                    "id": 1,
                    "user": {"login": "fullsend-ai-review[bot]", "type": "Bot"},
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
    def test_api_payload_text_is_never_in_retained_report(self):
        import json

        result = g.observe(26, FixtureClient())
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(result))
        self.assertTrue(result["fullsend_review_metadata_present"])
        self.assertEqual(
            [x["shadow"]["decision"] for x in result["results"]], ["hold", "hold"]
        )
        self.assertFalse(result["mutation_permitted"])

    def test_summary_explains_holds_without_raw_api_text(self):
        report = g.observe(26, FixtureClient())
        text = g.summary(report)
        self.assertIn("no merge authority", text)
        self.assertIn("Repository readiness", text)
        self.assertIn("PR candidate", text)
        self.assertIn("gemara-sdk: hold", text)
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", text)
        self.assertIn("not native Gemara Policy execution", text)

    def test_changed_candidate_and_closed_pr_cannot_pass(self):
        for client in [FixtureClient(changed=True), FixtureClient(closed=True)]:
            result = g.observe(26, client)
            for adapter in result["results"]:
                self.assertEqual(adapter["shadow"]["decision"], "hold")
                self.assertIn(
                    "candidate_not_current_open_pr", adapter["shadow"]["reasons"]
                )

    def test_current_revision_and_latest_decisive_review_required(self):
        review = {
            "id": 1,
            "user": {"login": "fullsend-ai-review[bot]", "type": "Bot"},
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

    def test_protected_policy_change_not_classified_as_harmless_docs(self):
        values, _ = g.normalize(pr(), [], [], [{"filename": ".fullsend/config.yaml"}])
        self.assertFalse(values["AM-PROTECTED"])
        self.assertIsNone(values["AM-CLASS"])

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


if __name__ == "__main__":
    unittest.main()
