import copy
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest import mock

import live_pilot as p
from platform_lab import InputError, assess, digest


def maintenance_client(get):
    client = mock.Mock()

    def route(path):
        if path.endswith("/pulls/32"):
            return {"user": {"login": "author"}, "head": {"sha": "a" * 40}}
        return get(path)

    client.get.side_effect = route
    client.pages.side_effect = lambda path: (
        [{"author": {"login": "author"}}]
        if path.endswith("/commits")
        else [
            {
                "id": 90,
                "state": "APPROVED",
                "commit_id": "a" * 40,
                "user": {"login": "reviewer", "type": "User"},
            }
        ]
    )
    return client


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
                "require_code_owner_review": True,
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

    def test_configuration_is_bounded_closed_and_has_an_independent_kill_switch(self):
        data = {
            "schema_version": "repository-merge-pilot/v1",
            "repository": p.REPO,
            "automatic_enabled": True,
            "automatic_expires_at": "2026-10-22T18:00:00Z",
            "maintenance_enabled": True,
            "allowed_document_paths": [p.DOCUMENT],
            "maximum_changed_lines": 20,
            "maintenance_maximum_age_seconds": 3600,
        }
        with mock.patch.object(p, "load", return_value=data):
            self.assertEqual(p.configuration(), data)
        for field, value in [
            ("automatic_enabled", "true"),
            ("repository", "other/repo"),
            ("maximum_changed_lines", 21),
            ("maximum_changed_lines", True),
            ("maintenance_maximum_age_seconds", 3601),
            ("allowed_document_paths", [".github/workflows/run.yml"]),
        ]:
            with (
                mock.patch.object(p, "load", return_value=dict(data, **{field: value})),
                self.assertRaises(InputError),
            ):
                p.configuration()
        with (
            mock.patch.object(p, "load", return_value=dict(data, unexpected=True)),
            self.assertRaises(InputError),
        ):
            p.configuration()
        with mock.patch.object(
            p, "load", return_value=dict(data, automatic_enabled=False)
        ):
            self.assertFalse(p.configuration()["automatic_enabled"])

    def test_maintenance_dispatch_cannot_be_replayed_for_other_revisions_or_sources(
        self,
    ):
        now = datetime.now(timezone.utc)
        run = {
            "id": 1,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "path": ".github/workflows/autonomy-pilot.yml",
            "head_sha": "b" * 40,
            "repository": {"full_name": p.REPO},
            "display_title": f"Gemara maintenance execute PR #32 @{'a' * 40}",
            "created_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "status": "completed",
            "conclusion": "success",
        }
        self.assertTrue(
            p.maintenance_run_matches(run, 32, "a" * 40, "b" * 40, 3600, True)
        )
        for args in [
            (33, "a" * 40, "b" * 40),
            (32, "c" * 40, "b" * 40),
            (32, "a" * 40, "c" * 40),
        ]:
            self.assertFalse(p.maintenance_run_matches(run, *args, 3600, True))
        for change in [
            {"display_title": f"Gemara maintenance evaluate PR #32 @{'a' * 40}"},
            {"event": "pull_request_target"},
            {"path": ".github/workflows/ci.yml"},
            {"conclusion": "failure"},
            {"repository": {"full_name": "other/repo"}},
            {"created_at": (now - timedelta(hours=2)).isoformat()},
        ]:
            self.assertFalse(
                p.maintenance_run_matches(
                    dict(run, **change), 32, "a" * 40, "b" * 40, 3600, True
                )
            )

    def test_maintenance_requires_current_maintainer_permission(self):
        config = {"maintenance_enabled": True, "maintenance_maximum_age_seconds": 3600}
        run = {
            "id": 1,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "path": ".github/workflows/autonomy-pilot.yml",
            "head_sha": "b" * 40,
            "repository": {"full_name": p.REPO},
            "display_title": f"Gemara maintenance execute PR #32 @{'a' * 40}",
            "created_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "actor": {"login": "owner"},
            "triggering_actor": {"login": "owner"},
        }
        for role, allowed in [
            ("write", False),
            ("read", False),
            ("admin", True),
            ("maintain", True),
        ]:
            client = maintenance_client(
                lambda path: run
                if "/actions/" in path
                else {
                    "permission": "write" if role == "maintain" else role,
                    "role_name": role,
                }
            )
            with mock.patch.dict(
                os.environ, {"PILOT_MAINTENANCE": "true", "GITHUB_RUN_ID": "1"}
            ):
                self.assertEqual(
                    bool(
                        p.maintenance_authorization(
                            client, 32, "a" * 40, "b" * 40, "enroll", config
                        )
                    ),
                    allowed,
                )

    def test_a_successful_skipped_or_probe_workflow_is_not_maintenance_approval(self):
        config = {"maintenance_enabled": True, "maintenance_maximum_age_seconds": 3600}
        run = {
            "id": 1,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "path": ".github/workflows/autonomy-pilot.yml",
            "head_sha": "b" * 40,
            "repository": {"full_name": p.REPO},
            "display_title": f"Gemara maintenance execute PR #32 @{'a' * 40}",
            "created_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "actor": {"login": "owner"},
            "triggering_actor": {"login": "owner"},
            "status": "completed",
            "conclusion": "success",
        }
        job = {
            "name": "evaluate",
            "run_id": 1,
            "head_sha": "b" * 40,
            "status": "completed",
            "conclusion": "success",
        }
        for jobs, allowed in [
            ([job, dict(job, name="enqueue / writer")], True),
            ([job], False),
            ([job, dict(job, name="enqueue / writer", conclusion="skipped")], False),
            ([], False),
            ([dict(job, conclusion="skipped")], False),
            ([dict(job, head_sha="c" * 40)], False),
            ([dict(job, run_id=2)], False),
        ]:

            def get(path):
                if "/actions/workflows/" in path:
                    return {"workflow_runs": [run]}
                if "/jobs?" in path:
                    return {"total_count": len(jobs), "jobs": jobs}
                return {"permission": "admin", "role_name": "admin"}

            client = maintenance_client(get)
            self.assertEqual(
                bool(
                    p.maintenance_authorization(
                        client, 32, "a" * 40, "b" * 40, "queue", config
                    )
                ),
                allowed,
            )

    def test_maintenance_tree_does_not_allow_unapproved_files_or_symlinks(self):
        base = {"code.py": ("blob", "100644", "a" * 40)}
        reviewed = dict(base, **{"docs/maintenance.md": ("blob", "100644", "b" * 40)})
        files = [{"filename": "docs/maintenance.md", "status": "added", "changes": 10}]
        self.assertTrue(p.maintenance_tree(base, reviewed, reviewed, files))
        self.assertFalse(
            p.maintenance_tree(
                base,
                reviewed,
                dict(reviewed, extra=("blob", "100644", "c" * 40)),
                files,
            )
        )
        symlink = dict(base, **{"docs/maintenance.md": ("blob", "120000", "b" * 40)})
        self.assertFalse(p.maintenance_tree(base, symlink, symlink, files))
        self.assertFalse(
            p.maintenance_scope(
                [{"filename": "outside.py", "status": "added", "changes": 1}]
            )
        )
        self.assertFalse(
            p.maintenance_scope([dict(files[0], previous_filename="old.yml")])
        )

    def test_maintenance_deletions_require_regular_base_entries(self):
        name = "docs/removed.md"
        files = [{"filename": name, "status": "removed", "changes": 1}]
        for kind, mode, allowed in [
            ("blob", "100644", True),
            ("blob", "100755", True),
            ("blob", "120000", False),
            ("commit", "160000", False),
        ]:
            self.assertEqual(
                p.maintenance_tree({name: (kind, mode, "a" * 40)}, {}, {}, files),
                allowed,
            )

    def test_maintenance_lookup_paginates_and_accepts_a_completed_evaluation_in_a_running_writer(
        self,
    ):
        now = datetime.now(timezone.utc)
        run = {
            "id": 101,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "path": ".github/workflows/autonomy-pilot.yml",
            "head_sha": "b" * 40,
            "repository": {"full_name": p.REPO},
            "display_title": f"Gemara maintenance execute PR #32 @{'a' * 40}",
            "created_at": (now - timedelta(seconds=100))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "actor": {"login": "owner"},
            "triggering_actor": {"login": "owner"},
            "status": "in_progress",
            "conclusion": None,
        }
        newer = [
            dict(
                run,
                id=i + 1,
                display_title="Read-only probe",
                created_at=(now - timedelta(seconds=i))
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            )
            for i in range(100)
        ]
        job = {
            "name": "evaluate",
            "run_id": 101,
            "head_sha": "b" * 40,
            "status": "completed",
            "conclusion": "success",
        }

        def get(path):
            if "/actions/workflows/" in path:
                return {"workflow_runs": newer if path.endswith("page=1") else [run]}
            if "/jobs?" in path:
                return {
                    "total_count": 2,
                    "jobs": [job, dict(job, name="enqueue / writer")],
                }
            return {"permission": "admin"}

        client = maintenance_client(get)
        config = {"maintenance_enabled": True, "maintenance_maximum_age_seconds": 3600}
        self.assertIsNotNone(
            p.maintenance_authorization(client, 32, "a" * 40, "b" * 40, "queue", config)
        )
        self.assertTrue(
            any(call.args[0].endswith("page=2") for call in client.get.call_args_list)
        )

    def test_maintenance_never_changes_its_own_governance(self):
        for path in [
            ".github/workflows/autonomy-queue.yml",
            ".github/workflows/ci.yml",
            ".fullsend/config.yaml",
            "experiments/autonomy-platform/policies/pilot-config.json",
            "scripts/validate_example.py",
            "AGENTS.md",
        ]:
            self.assertFalse(
                p.maintenance_scope(
                    [{"filename": path, "status": "modified", "changes": 1}]
                )
            )

    def test_maintenance_requires_independent_current_human_approval(self):
        client = maintenance_client(
            lambda path: {"role_name": "maintain", "permission": "write"}
        )
        self.assertIsNotNone(p.independent_maintenance_approval(client, 32, "a" * 40))
        approval = {
            "id": 90,
            "state": "APPROVED",
            "commit_id": "a" * 40,
            "user": {"login": "reviewer", "type": "User"},
        }
        for change in [
            {"commit_id": "c" * 40},
            {"state": "CHANGES_REQUESTED"},
            {"user": {"login": "author", "type": "User"}},
            {"user": {"login": "reviewer", "type": "Bot"}},
        ]:
            client.pages.side_effect = lambda path: (
                [{"author": {"login": "author"}}]
                if path.endswith("/commits")
                else [dict(approval, **change)]
            )
            self.assertIsNone(p.independent_maintenance_approval(client, 32, "a" * 40))
        client.pages.side_effect = lambda path: (
            [{"author": {"login": "reviewer"}}]
            if path.endswith("/commits")
            else [approval]
        )
        self.assertIsNone(p.independent_maintenance_approval(client, 32, "a" * 40))
        client.pages.side_effect = lambda path: (
            [{"author": {"login": "author"}}]
            if path.endswith("/commits")
            else [approval, dict(approval, id=91, state="DISMISSED")]
        )
        self.assertIsNone(p.independent_maintenance_approval(client, 32, "a" * 40))

    def test_maintenance_native_policy_still_requires_authority_ci_and_exact_tree(self):
        bundle = p.bundle(True)
        subject = {
            "repository": p.REPO,
            "branch": "main",
            "configuration_sha256": "c" * 64,
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
        }
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
        self.assertNotIn("LP-CANDIDATE", obs)
        self.assertEqual(
            assess(bundle, "candidate", subject, obs, now)["decision"], "eligible"
        )
        for key in obs:
            bad = copy.deepcopy(obs)
            bad[key]["value"] = False
            self.assertEqual(
                assess(bundle, "candidate", subject, bad, now)["decision"], "hold"
            )

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
        automatic = copy.deepcopy(good)
        automatic[3]["parameters"]["required_approving_review_count"] = 0
        self.assertTrue(p.queue_rules(automatic))
        for index, key, value in [
            (2, "max_entries_to_merge", 5),
            (2, "max_entries_to_build", 5),
            (3, "required_approving_review_count", -1),
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

    def test_unknown_mergeability_draft_and_foreign_heads_hold(self):
        pr = {
            "state": "open",
            "draft": False,
            "mergeable": True,
            "head": {"sha": "a" * 40, "repo": {"full_name": p.REPO}},
            "base": {"ref": "main", "repo": {"full_name": p.REPO}},
        }
        self.assertTrue(p.current_pr(pr, "a" * 40))
        for key, value in [
            ("mergeable", None),
            ("mergeable", False),
            ("draft", True),
            ("state", "closed"),
        ]:
            self.assertFalse(p.current_pr(dict(pr, **{key: value}), "a" * 40))
        bad = copy.deepcopy(pr)
        bad["head"]["repo"]["full_name"] = "other/repo"
        self.assertFalse(p.current_pr(bad, "a" * 40))
        self.assertFalse(p.current_pr(pr, "b" * 40))

    def test_passing_ci_and_candidate_do_not_override_the_native_scope_hold(self):
        head, base = "a" * 40, "b" * 40
        pr = {
            "state": "open",
            "draft": False,
            "mergeable": True,
            "head": {"sha": head, "repo": {"full_name": p.REPO}},
            "base": {"ref": "main", "repo": {"full_name": p.REPO}},
        }
        config = {
            "automatic_enabled": True,
            "automatic_expires_at": "2026-10-22T18:00:00Z",
            "maintenance_enabled": True,
            "maximum_changed_lines": 20,
        }
        rows = [
            {
                "name": n,
                "head_sha": head,
                "app": {"id": 15368},
                "status": "completed",
                "conclusion": "success",
            }
            for n in p.CHECKS
        ]
        client = mock.Mock()
        client.errors = set()
        client.get.side_effect = (
            lambda path: pr
            if path.endswith("pulls/32")
            else (
                {"commit": {"sha": base}}
                if path.endswith("branches/main") and "/rules/" not in path
                else rules()
            )
        )
        client.pages.side_effect = (
            lambda path, key=None: [
                {"filename": "docs/not-in-pilot.md", "status": "added", "changes": 1}
            ]
            if path.endswith("/files")
            else rows
        )
        report = {
            "stable_during_collection": True,
            "head_sha": head,
            "base_sha": base,
            "candidate_decision": "eligible",
            "readiness_decision": "hold",
            "shadow": {"evaluation": {"request_sha256": "c" * 64}},
        }
        with (
            mock.patch.dict(
                os.environ, {"PILOT_MAINTENANCE": "false", "PILOT_CAN_ENQUEUE": "true"}
            ),
            mock.patch.object(p, "configuration", return_value=config),
            mock.patch.object(p, "maintenance_authorization", return_value=None),
            mock.patch.object(p.g, "observe", return_value=report),
            mock.patch.object(p, "trusted_source", return_value=True),
            mock.patch.object(
                p, "tree", return_value={p.DOCUMENT: ("blob", "100644", "d" * 40)}
            ),
            mock.patch.object(p, "discussions_clear", return_value=True),
        ):
            result = p.evaluate(32, head, "enroll", client)
            self.assertEqual(result["decision"], "hold")
            assessment = {
                r["id"]: r["state"] for r in result["evaluation"]["assessments"]
            }
            self.assertEqual(assessment["LP-CI"], "passed")
            self.assertEqual(assessment["LP-CANDIDATE"], "passed")
            self.assertEqual(assessment["LP-SCOPE"], "failed")
            with mock.patch.object(
                p,
                "configuration",
                return_value=dict(config, automatic_expires_at="2020-01-01T00:00:00Z"),
            ):
                expired = p.evaluate(32, head, "enroll", client)
            self.assertEqual(
                {r["id"]: r["state"] for r in expired["evaluation"]["assessments"]}[
                    "LP-AUTH"
                ],
                "failed",
            )
            with mock.patch.object(p.subprocess, "run") as writer:
                with self.assertRaises(InputError):
                    p.enqueue(result)
                writer.assert_not_called()

    def test_read_only_policy_hold_is_success_but_execution_and_errors_fail(self):
        result = {
            "decision": "hold",
            "evaluated_sha": "a" * 40,
            "production_readiness": "hold",
            "evaluation": {"assessments": []},
        }
        args = ["pilot", "--phase", "enroll", "--pr", "32", "--head", "a" * 40]
        with (
            mock.patch("sys.argv", args),
            mock.patch.object(p, "evaluate", return_value=result),
            mock.patch("builtins.print"),
            mock.patch.object(p, "enqueue") as writer,
        ):
            self.assertEqual(p.main(), 0)
            writer.assert_not_called()
        with (
            mock.patch("sys.argv", args + ["--execute"]),
            mock.patch.object(p, "evaluate", return_value=result),
            mock.patch("builtins.print"),
            mock.patch.object(p, "enqueue") as writer,
        ):
            self.assertEqual(p.main(), 2)
            writer.assert_not_called()
        with (
            mock.patch("sys.argv", args),
            mock.patch.object(p, "evaluate", side_effect=InputError("fixture_error")),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(p.main(), 2)

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
            mock.patch.dict(
                os.environ,
                {
                    "PILOT_CAN_ENQUEUE": "true",
                    "PILOT_ENQUEUE_TOKEN": "test-installation-token",
                },
            ),
            mock.patch.object(p.urllib.request, "build_opener") as opener,
            mock.patch.object(
                p.subprocess, "run", return_value=mock.Mock(returncode=0)
            ) as run,
        ):
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"total_count":1,"repositories":[{"full_name":"fullsend-ai/auto-merge"}]}'
            opener.return_value.open.return_value.__enter__.return_value.status = 200
            self.assertEqual(p.enqueue(result), "native_auto_merge_requested")
            self.assertEqual(
                run.call_args.kwargs["env"]["GH_TOKEN"], "test-installation-token"
            )
            self.assertNotIn("PILOT_ENQUEUE_TOKEN", run.call_args.kwargs["env"])
            command = run.call_args.args[0]
            self.assertIn("--match-head-commit", command)
            self.assertNotIn("--admin", command)
            self.assertNotIn("mergePullRequest", " ".join(command))

    def test_missing_or_cross_repository_app_token_never_requests_a_merge(self):
        result = {
            "decision": "eligible",
            "stage": "enroll",
            "pull_request": 32,
            "reviewed_head": "a" * 40,
        }
        with (
            mock.patch.dict(
                os.environ, {"PILOT_CAN_ENQUEUE": "true", "PILOT_ENQUEUE_TOKEN": ""}
            ),
            mock.patch.object(p.subprocess, "run") as run,
        ):
            with self.assertRaises(InputError):
                p.enqueue(result)
            run.assert_not_called()
        with (
            mock.patch.dict(
                os.environ,
                {
                    "PILOT_CAN_ENQUEUE": "true",
                    "PILOT_ENQUEUE_TOKEN": "test-installation-token",
                },
            ),
            mock.patch.object(p.urllib.request, "build_opener") as opener,
            mock.patch.object(p.subprocess, "run") as run,
        ):
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"total_count":2,"repositories":[{"full_name":"fullsend-ai/auto-merge"},{"full_name":"other/repo"}]}'
            with self.assertRaises(InputError):
                p.enqueue(result)
            run.assert_not_called()

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
