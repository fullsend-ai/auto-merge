import copy
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest import mock

import live_pilot as p
from platform_lab import InputError, assess, digest


def rules():
    return [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "merge_queue",
            "parameters": {"max_entries_to_merge": 1, "max_entries_to_build": 1},
        },
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": True,
                "required_review_thread_resolution": True,
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": n, "integration_id": 15368}
                    for n in p.CHECKS | {p.QUEUE_CHECK}
                ],
            },
        },
    ]


class PilotTests(unittest.TestCase):
    def test_native_lab_policy_all_required_conditions(self):
        subject = {
            "repository": p.REPO,
            "branch": "main",
            "configuration_sha256": "c" * 64,
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
        }
        bundle = p.bundle()
        now = "2026-10-15T14:00:00Z"
        obs = {
            c["id"]: {
                "subject_sha256": digest(subject),
                "collected_at": now,
                "trusted_source": True,
                "value": True,
            }
            for c in next(iter(bundle["catalogs"].values()))["controls"]
        }
        self.assertEqual(
            assess(bundle, "candidate", subject, obs, now)["decision"], "eligible"
        )
        for key in obs:
            bad = copy.deepcopy(obs)
            bad[key]["value"] = False
            self.assertEqual(
                assess(bundle, "candidate", subject, bad, now)["decision"], "hold"
            )

    def test_grant_is_exact_expiring_and_closed_schema(self):
        data = {
            "schema_version": "lab-merge-grant/v1",
            "repository": p.REPO,
            "enabled": True,
            "pull_request": 30,
            "head_sha": "a" * 40,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "maximum_changed_lines": 12,
        }
        with mock.patch.object(p, "load", return_value=data):
            self.assertEqual(p.grant(), data)
        for field, value in [
            ("enabled", False),
            ("head_sha", "bad"),
            ("repository", "other/repo"),
            ("maximum_changed_lines", 21),
            ("pull_request", True),
            ("expires_at", "2000-01-01T00:00:00Z"),
        ]:
            bad = dict(data)
            bad[field] = value
            with (
                mock.patch.object(p, "load", return_value=bad),
                self.assertRaises(InputError),
            ):
                p.grant()
        with (
            mock.patch.object(p, "load", return_value=dict(data, unexpected=True)),
            self.assertRaises(InputError),
        ):
            p.grant()

    def test_only_one_regular_reviewed_document_can_enter_queue_tree(self):
        base = {
            p.DOCUMENT: ("blob", "100644", "a" * 40),
            "code.py": ("blob", "100644", "b" * 40),
        }
        reviewed = dict(base)
        reviewed[p.DOCUMENT] = ("blob", "100644", "c" * 40)
        self.assertTrue(p.exact_tree(base, reviewed, reviewed))
        for change in [
            {"extra.py": ("blob", "100644", "d" * 40)},
            {"code.py": ("blob", "100644", "d" * 40)},
            {p.DOCUMENT: ("blob", "120000", "c" * 40)},
            {p.DOCUMENT: ("blob", "100644", "f" * 40)},
        ]:
            self.assertFalse(p.exact_tree(base, reviewed, dict(reviewed, **change)))
        symlink = dict(reviewed)
        symlink[p.DOCUMENT] = ("blob", "120000", "c" * 40)
        self.assertFalse(p.exact_tree(base, symlink, symlink))

    def test_queue_protections_cannot_be_relaxed(self):
        good = rules()
        self.assertTrue(p.queue_rules(good))
        for index, key, value in [
            (2, "max_entries_to_merge", 5),
            (2, "max_entries_to_build", 5),
            (3, "required_approving_review_count", 0),
            (3, "required_review_thread_resolution", False),
            (4, "strict_required_status_checks_policy", False),
        ]:
            bad = copy.deepcopy(good)
            bad[index]["parameters"][key] = value
            self.assertFalse(p.queue_rules(bad))
        bad = copy.deepcopy(good)
        bad[-1]["parameters"]["required_status_checks"] = [
            {"context": p.QUEUE_CHECK, "integration_id": 99}
        ]
        self.assertFalse(p.queue_rules(bad))

    def test_pending_or_spoofed_ci_is_not_queue_success(self):
        rows = [
            {
                "name": n,
                "head_sha": "a" * 40,
                "app": {"id": 15368},
                "status": "completed",
                "conclusion": "success",
            }
            for n in p.CHECKS
        ]
        self.assertTrue(p.checks_pass(rows, "a" * 40))
        self.assertFalse(p.checks_pass(rows, "b" * 40))
        rows[0]["app"]["id"] = 99
        self.assertFalse(p.checks_pass(rows, "a" * 40))
        rows[0]["app"]["id"] = 15368
        rows[0]["status"] = "in_progress"
        self.assertFalse(p.checks_pass(rows, "a" * 40))

    def test_a_held_native_result_never_calls_the_writer(self):
        with (
            mock.patch.dict(os.environ, {"PILOT_CAN_ENQUEUE": "true"}),
            mock.patch.object(p.subprocess, "run") as run,
        ):
            with self.assertRaises(InputError):
                p.enqueue({"decision": "hold", "stage": "enroll"})
            run.assert_not_called()

    def test_queue_request_uses_expected_head_and_never_admin(self):
        result = {
            "decision": "eligible",
            "stage": "enroll",
            "pull_request": 30,
            "reviewed_head": "a" * 40,
        }
        with (
            mock.patch.dict(os.environ, {"PILOT_CAN_ENQUEUE": "true"}),
            mock.patch.object(
                p.subprocess, "run", return_value=mock.Mock(returncode=0)
            ) as run,
        ):
            self.assertEqual(p.enqueue(result), "queue_request_submitted")
            command = run.call_args.args[0]
            self.assertIn("--match-head-commit", command)
            self.assertNotIn("--admin", command)
            self.assertNotIn("mergePullRequest", " ".join(command))

    def test_queue_entry_binds_both_reviewed_and_actual_group_commits(self):
        entry = {
            "position": 1,
            "pullRequest": {"number": 30, "headRefOid": "a" * 40},
            "baseCommit": {"oid": "b" * 40},
            "headCommit": {"oid": "c" * 40},
        }
        self.assertTrue(p.queue_entry_matches(entry, 30, "a" * 40, "b" * 40, "c" * 40))
        for args in [
            (31, "a" * 40, "b" * 40, "c" * 40),
            (30, "d" * 40, "b" * 40, "c" * 40),
            (30, "a" * 40, "d" * 40, "c" * 40),
            (30, "a" * 40, "b" * 40, "d" * 40),
        ]:
            self.assertFalse(p.queue_entry_matches(entry, *args))
        self.assertFalse(p.queue_entry_matches(None, 30, "a" * 40, "b" * 40, "c" * 40))

    def test_group_identity_is_closed_to_one_pr_and_base(self):
        self.assertIsNotNone(
            p.GROUP_REF.fullmatch("refs/heads/gh-readonly-queue/main/pr-30-" + "a" * 40)
        )
        for text in [
            "refs/heads/main",
            "refs/heads/gh-readonly-queue/other/pr-30-" + "a" * 40,
            "refs/heads/gh-readonly-queue/main/pr-30-" + "a" * 40 + "/extra",
        ]:
            self.assertIsNone(p.GROUP_REF.fullmatch(text))
