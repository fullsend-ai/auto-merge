"""Adversarial tests for the boundary between shared assessment and existing writer."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from unittest import mock
import unittest
import zipfile

import shared_gate as s
import authorize_auto_merge as pilot
from policy_evaluation import InputError, digest


class SharedReceiptTests(unittest.TestCase):
    def setUp(self):
        self.c = s.settings()
        self.head = "a" * 40
        self.base = "b" * 40
        self.run = dict(
            id=100,
            run_attempt=1,
            path=".github/workflows/gemara-auto-merge.yml",
            repository={"full_name": s.g.REPOSITORY},
            head_sha=self.base,
            event="workflow_dispatch",
        )
        self.client = mock.Mock()
        self.client.errors = set()
        self.client.get.return_value = self.run
        self.client.pages.return_value = [
            {
                "name": "shared / Assess shared merge requirements",
                "status": "completed",
                "conclusion": "success",
            }
        ]
        fmt = lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ")
        now = datetime.now(timezone.utc)
        self.quality = dict(
            collected_at=fmt(now),
            latest_score_at=fmt(now - timedelta(days=1)),
            passed=99,
            total=100,
        )
        ctx = dict(
            repository=s.g.REPOSITORY,
            pr=53,
            head_sha=self.head,
            source_sha=self.base,
            phase="enroll",
            evaluated_sha=self.head,
            run_id="100",
            attempt="1",
            config_sha256=digest(self.c),
            collected_at=fmt(now),
            ruleset_audit={"synthetic": True},
        )
        subject = dict(
            identity=self.c["binding"]["identity"],
            change=53,
            head_sha=self.head,
            target_sha=self.base,
            policy_sha256=self.c["candidate_policy_sha256"],
            binding_sha256=s.binding_digest(self.c["binding"]),
        )
        candidate = dict(
            subject=subject,
            engine="gemara",
            evidence_kind="collector-observation",
            authorization="none",
            mutation_permitted=False,
            binding_sha256=subject["binding_sha256"],
            policy_sha256=subject["policy_sha256"],
            catalog_sha256=self.c["candidate_catalog_sha256"],
            decision="eligible",
            assessments=[
                dict(id=k, state="passed")
                for k in [
                    "OWNER-SCOPE",
                    "REVIEW-CLEAR",
                    "CHECKS-PASS",
                    "EVIDENCE-CURRENT",
                    "PROTECTIONS-ACTIVE",
                ]
            ],
        )
        judge = dict(
            schema_version="judge-check/v1",
            authorization="none",
            mutation_permitted=False,
            minimum_basis_points=9900,
            passed=99,
            total=100,
            state="passed",
            decision="eligible",
        )
        self.report = dict(
            schema_version="candidate-assessment/v1",
            authorization="none",
            mutation_permitted=False,
            decision="eligible",
            candidate=candidate,
            quality=judge,
        )
        self.receipt = dict(
            context=ctx,
            quality=self.quality,
            quality_sha256=digest(self.quality),
            assessment_sha256=digest(self.report),
        )
        self.files = {"receipt.json": self.receipt, "assessment.json": self.report}

    def verify(self):
        with mock.patch.dict(
            os.environ, {"GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1"}
        ), mock.patch.object(s, "artifact", return_value=self.files), mock.patch.object(
            s, "verify_ruleset_audit"
        ):
            return s.verify_assessment(
                self.client, 53, self.head, self.base, "enroll", self.head
            )

    def reseal(self):
        self.receipt["quality_sha256"] = digest(self.receipt["quality"])
        self.receipt["assessment_sha256"] = digest(self.report)

    def test_valid_receipt_and_below_threshold_hold(self):
        self.assertEqual(self.verify()["decision"], "eligible")
        self.report["quality"].update(state="failed", decision="hold", passed=94)
        self.quality["passed"] = 94
        self.report["decision"] = "hold"
        self.reseal()
        self.assertEqual(self.verify()["decision"], "hold")

    def test_current_run_identity_attempt_and_completed_job_required(self):
        for field, value in [
            ("head_sha", "c" * 40),
            ("run_attempt", 2),
            ("event", "pull_request"),
            ("path", ".github/workflows/fake.yml"),
        ]:
            with self.subTest(field=field):
                original = self.run[field]
                self.run[field] = value
                with self.assertRaises(InputError):
                    self.verify()
                self.run[field] = original
        self.client.pages.return_value = []
        with self.assertRaises(InputError):
            self.verify()

    def test_receipt_binds_all_subject_and_configuration_fields(self):
        for field, value in [
            ("pr", 54),
            ("head_sha", "c" * 40),
            ("source_sha", "c" * 40),
            ("evaluated_sha", "c" * 40),
            ("phase", "queue"),
            ("run_id", "101"),
            ("attempt", "2"),
            ("config_sha256", "c" * 64),
        ]:
            with self.subTest(field=field):
                original = self.receipt["context"][field]
                self.receipt["context"][field] = value
                with self.assertRaises(InputError):
                    self.verify()
                self.receipt["context"][field] = original

    def test_stale_and_future_candidate_or_quality_receipts_hold(self):
        for container, field, seconds in [
            (self.receipt["context"], "collected_at", 901),
            (self.receipt["context"], "collected_at", -60),
            (self.quality, "collected_at", 901),
            (self.quality, "latest_score_at", 604801),
        ]:
            original = container[field]
            container[field] = (
                datetime.now(timezone.utc) - timedelta(seconds=seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.reseal()
            with self.subTest(field=field, seconds=seconds), self.assertRaises(
                InputError
            ):
                self.verify()
            container[field] = original
            self.reseal()

    def test_report_digest_privilege_and_incomplete_controls_rejected(self):
        self.report["decision"] = "hold"
        with self.assertRaises(InputError):
            self.verify()
        self.report["decision"] = "eligible"
        self.report["mutation_permitted"] = True
        self.reseal()
        with self.assertRaises(InputError):
            self.verify()
        self.report["mutation_permitted"] = False
        self.report["candidate"]["assessments"].pop()
        self.reseal()
        with self.assertRaises(InputError):
            self.verify()

    def test_passing_decision_cannot_mask_failed_control_or_quality(self):
        self.report["candidate"]["assessments"][0]["state"] = "failed"
        self.reseal()
        with self.assertRaises(InputError):
            self.verify()
        self.report["candidate"]["assessments"][0]["state"] = "passed"
        self.report["quality"]["state"] = "unknown"
        self.reseal()
        with self.assertRaises(InputError):
            self.verify()

    def test_artifact_digest_run_layout_and_duplicate_entries_rejected(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("receipt.json", "{}")
            z.writestr("assessment.json", "{}")
        raw = archive.getvalue()
        a = dict(
            id=7,
            name="result",
            expired=False,
            size_in_bytes=len(raw),
            workflow_run={"id": 100, "head_sha": self.base},
            digest="sha256:" + hashlib.sha256(raw).hexdigest(),
        )
        self.client.pages.return_value = [a]
        with mock.patch.object(s.native, "download", return_value=raw):
            self.assertEqual(
                set(
                    s.artifact(
                        self.client,
                        self.run,
                        "result",
                        ["receipt.json", "assessment.json"],
                    )
                ),
                {"receipt.json", "assessment.json"},
            )
            a["digest"] = "sha256:" + "0" * 64
            with self.assertRaises(InputError):
                s.artifact(
                    self.client, self.run, "result", ["receipt.json", "assessment.json"]
                )
            a["digest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
            a["workflow_run"]["id"] = 101
            with self.assertRaises(InputError):
                s.artifact(
                    self.client, self.run, "result", ["receipt.json", "assessment.json"]
                )

    def test_writer_rechecks_shared_hold_before_any_mutation(self):
        config = pilot.configuration()
        result = dict(
            mode="automatic",
            configuration_sha256=digest(config),
            pull_request=53,
            reviewed_head=self.head,
            base_sha=self.base,
        )
        pr = dict(
            state="open",
            draft=False,
            mergeable=True,
            head={"sha": self.head, "repo": {"full_name": pilot.REPO}},
            base={"ref": "main", "repo": {"full_name": pilot.REPO}},
        )
        self.client.get.side_effect = lambda path: (
            pr if path.endswith("/pulls/53") else {"commit": {"sha": self.base}}
        )
        with mock.patch.object(
            pilot.shared_gate, "verify_assessment", return_value={"decision": "hold"}
        ), mock.patch.object(pilot, "pending_queue_request") as mutate:
            with self.assertRaisesRegex(
                InputError, "shared_policy_held_before_enqueue"
            ):
                pilot.pre_enqueue(result, self.client)
            mutate.assert_not_called()

    def test_initial_evaluation_holds_when_legacy_checks_all_pass_but_quality_fails(
        self,
    ):
        from test_authorize_auto_merge import rules

        head, base = self.head, self.base
        config = pilot.configuration()
        config["automatic_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        pr = dict(
            state="open",
            draft=False,
            mergeable=True,
            head={"sha": head, "repo": {"full_name": pilot.REPO}},
            base={"ref": "main", "repo": {"full_name": pilot.REPO}},
        )
        client = mock.Mock()
        client.errors = set()
        client.get.side_effect = lambda path: (
            pr
            if path.endswith("/pulls/53")
            else (
                {"commit": {"sha": base}}
                if path.endswith("/branches/main") and "/rules/" not in path
                else rules()
            )
        )
        rows = [
            dict(
                name=n,
                head_sha=head,
                app={"id": 15368},
                status="completed",
                conclusion="success",
            )
            for n in pilot.CHECKS
        ]
        client.pages.side_effect = lambda path, key=None: (
            [{"filename": pilot.DOCUMENT, "status": "modified", "changes": 80}]
            if path.endswith("/files")
            else rows
        )
        report = dict(
            stable_during_collection=True,
            head_sha=head,
            base_sha=base,
            candidate_decision="eligible",
            readiness_decision="hold",
            shadow={"evaluation": {"request_sha256": "c" * 64}},
        )
        with mock.patch.dict(
            os.environ, {"PILOT_MAINTENANCE": "false"}
        ), mock.patch.object(
            pilot, "configuration", return_value=config
        ), mock.patch.object(
            pilot, "maintenance_authorization", return_value=None
        ), mock.patch.object(
            pilot.g, "observe", return_value=report
        ), mock.patch.object(
            pilot, "trusted_source", return_value=True
        ), mock.patch.object(
            pilot, "tree", return_value={pilot.DOCUMENT: ("blob", "100644", "d" * 40)}
        ), mock.patch.object(
            pilot, "discussions_clear", return_value=True
        ), mock.patch.object(
            pilot.shared_gate, "verify_assessment", return_value={"decision": "hold"}
        ):
            result = pilot.evaluate(53, head, "enroll", client)
        self.assertTrue(
            all(r["state"] == "passed" for r in result["evaluation"]["assessments"])
        )
        self.assertEqual(result["decision"], "hold")
        self.assertEqual(result["authorized_action"], "none")
        with mock.patch.object(pilot.subprocess, "run") as writer:
            with self.assertRaises(InputError):
                pilot.enqueue(result)
            writer.assert_not_called()

    def test_missing_receipt_never_reaches_merge_command(self):
        result = dict(
            decision="eligible",
            stage="enroll",
            mode="automatic",
            configuration_sha256=digest(pilot.configuration()),
            pull_request=53,
            reviewed_head=self.head,
            base_sha=self.base,
        )
        with mock.patch.dict(
            os.environ,
            {"PILOT_CAN_ENQUEUE": "true", "PILOT_ENQUEUE_TOKEN": "SYNTHETIC"},
        ), mock.patch.object(pilot, "verify_scope"), mock.patch.object(
            pilot,
            "pre_enqueue",
            side_effect=InputError("shared_artifact_missing_or_ambiguous"),
        ), mock.patch.object(
            pilot.subprocess, "run"
        ) as command:
            with self.assertRaises(InputError):
                pilot.enqueue(result)
            command.assert_not_called()


class CandidateAdapterTests(unittest.TestCase):
    def setUp(self):
        self.head, self.base = "a" * 40, "b" * 40
        self.pr = dict(
            number=53,
            state="open",
            draft=False,
            mergeable=True,
            changed_files=1,
            head={"sha": self.head, "repo": {"full_name": pilot.REPO}},
            base={"sha": self.base, "ref": "main", "repo": {"full_name": pilot.REPO}},
        )
        self.proof = dict(
            reason="contract_verified",
            values={"AM-REVIEW": True, "AM-FINDINGS": True, "AM-RISK": 1},
            run_id=10,
            run_attempt=1,
            artifact_id=20,
            subject={"head_sha": self.head, "base_sha": self.base},
        )
        self.report = dict(
            stable_during_collection=True,
            head_sha=self.head,
            base_sha=self.base,
            native_review_evidence=self.proof,
        )
        self.client = mock.Mock()
        self.client.errors = set()

        def get(path):
            if path.endswith("/pulls/53"):
                return self.pr
            if path.endswith("/branches/main") and "/rules/" not in path:
                return {"commit": {"sha": self.base}, "protected": True}
            if path.endswith("/rulesets"):
                return [{"id": 1}]
            if path.endswith("/rulesets/1"):
                return {"enforcement": "active", "bypass_actors": []}
            if path.endswith("/artifacts/20"):
                return {"digest": "sha256:" + "c" * 64}
            return []

        self.client.get.side_effect = get
        self.client.pages.side_effect = lambda path, key=None: (
            [{"filename": pilot.DOCUMENT, "status": "modified"}]
            if path.endswith("/files")
            else [
                {
                    "name": n,
                    "head_sha": self.head,
                    "app": {"id": 15368},
                    "status": "completed",
                    "conclusion": "success",
                }
                for n in s.settings()["binding"]["required_checks"]
            ]
        )

    def collect(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(
            os.environ,
            {
                "PILOT_SOURCE_SHA": self.base,
                "GITHUB_RUN_ID": "100",
                "GITHUB_RUN_ATTEMPT": "1",
            },
        ), mock.patch.object(
            pilot, "trusted_source", return_value=True
        ), mock.patch.object(
            pilot, "tree", return_value={pilot.DOCUMENT: ("blob", "100644", "d" * 40)}
        ), mock.patch.object(
            pilot, "discussions_clear", return_value=True
        ), mock.patch.object(
            pilot, "queue_rules", return_value=True
        ), mock.patch.object(
            s.g, "observe", return_value=self.report
        ), mock.patch.object(
            s, "quality_snapshot", return_value=({}, {"synthetic": True})
        ):
            out = Path(d) / "inputs"
            s.collect(53, self.head, "enroll", out, self.client)
            return json.loads((out / "candidate.json").read_text())

    def test_authentic_subject_modes_required_checks_and_payload_binding(self):
        e = self.collect()
        self.assertEqual(e["subject"]["head_sha"], self.head)
        self.assertEqual(e["subject"]["target_sha"], self.base)
        self.assertEqual(e["review"]["risk_score"], 1)
        self.assertEqual(e["files"][0]["mode"], "100644")
        self.assertEqual(e["publication"]["artifact_sha256"], "c" * 64)
        self.assertEqual(len(e["checks"]), 3)
        self.assertFalse(e["protections"]["bypass_enabled"])

    def test_missing_risk_remains_unknown_not_zero(self):
        self.proof["values"]["AM-RISK"] = None
        self.assertIsNone(self.collect()["review"]["risk_score"])

    def test_wrong_review_head_or_unstable_collection_refused(self):
        self.proof["subject"]["head_sha"] = "c" * 40
        with self.assertRaises(InputError):
            self.collect()
        self.proof["subject"]["head_sha"] = self.head
        self.report["stable_during_collection"] = False
        with self.assertRaises(InputError):
            self.collect()

    def test_incomplete_file_listing_refused(self):
        self.pr["changed_files"] = 2
        with self.assertRaisesRegex(InputError, "shared_files_incomplete"):
            self.collect()


@unittest.skipUnless(
    os.environ.get("GITHUB_ACTIONS") == "true", "requires GitHub-hosted Linux isolation"
)
class HostedCombinedAssessmentTests(unittest.TestCase):
    def test_pinned_core_in_jail_holds_at_94_and_passes_at_99(self):
        import subprocess
        import tempfile
        from pathlib import Path

        adapter = CandidateAdapterTests()
        adapter.setUp()
        candidate = adapter.collect()
        config = copy.deepcopy(s.settings())
        instant = datetime.now(timezone.utc).replace(microsecond=0)
        fmt = lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Entire input is synthetic; do not extend the real owner grant for a test.
        config["binding"]["owner_grant_expires_at"] = fmt(instant + timedelta(days=1))
        candidate["subject"]["binding_sha256"] = s.binding_digest(config["binding"])
        candidate["publication"]["subject"] = candidate["subject"]
        context = dict(
            repository=s.g.REPOSITORY,
            pr=53,
            head_sha="a" * 40,
            source_sha="b" * 40,
            phase="enroll",
            evaluated_sha="a" * 40,
            run_id="100",
            attempt="1",
            config_sha256=digest(config),
            collected_at=fmt(instant),
            ruleset_audit={"synthetic": True},
        )
        quality = dict(
            schema_version="judge-observation/v1",
            scorer=config["judge_policy"]["scorer"],
            source_id=config["judge_policy"]["source_id"],
            experiment_id=config["judge_policy"]["experiment_id"],
            cohort="experiment-scored-approvals",
            window_start=fmt(instant - timedelta(days=365)),
            window_end=fmt(instant),
            collected_at=fmt(instant),
            latest_score_at=fmt(instant - timedelta(days=1)),
            passed=94,
            total=100,
            invalid=0,
            excluded_other_sources=0,
            complete=True,
            records_sha256="e" * 64,
            authorization="none",
            mutation_permitted=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            inputs = work / "input"
            inputs.mkdir()
            qdir = work / "quality"
            qdir.mkdir()
            for name, value in [
                ("config.json", config),
                ("candidate.json", candidate),
                ("context.json", context),
            ]:
                (inputs / name).write_text(json.dumps(value))
            (qdir / "quality-context.json").write_text(
                json.dumps(
                    dict(
                        source_sha="b" * 40,
                        run_id="100",
                        attempt="1",
                        config_sha256=digest(config),
                        ruleset_audit={"synthetic": True},
                    )
                )
            )
            for passed, decision in [(94, "hold"), (99, "eligible")]:
                quality["passed"] = passed
                (qdir / "quality.json").write_text(json.dumps(quality))
                output = work / str(passed)
                result = subprocess.run(
                    [
                        "/usr/bin/sudo",
                        "-n",
                        "/usr/bin/env",
                        "-i",
                        "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                        "/usr/bin/python3",
                        str(s.ROOT.parent / "scripts/shared_gate_runtime.py"),
                        "assess",
                        "--input",
                        str(inputs),
                        "--quality",
                        str(qdir),
                        "--output",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=240,
                )
                self.assertEqual(result.returncode, 0, result.stderr[-1500:])
                checked = subprocess.run(
                    [
                        "/usr/bin/sudo",
                        "-n",
                        "/usr/bin/cat",
                        str(output / "assessment.json"),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                report = json.loads(checked.stdout)
                self.assertEqual(report["candidate"]["decision"], "eligible")
                self.assertEqual(report["decision"], decision)
                self.assertEqual(len(report["candidate"]["assessments"]), 5)
                self.assertFalse(report["mutation_permitted"])
                # Root-owned reports must be removed before TemporaryDirectory cleanup.
                subprocess.run(
                    [
                        "/usr/bin/sudo",
                        "-n",
                        "/usr/bin/chown",
                        "--no-dereference",
                        str(os.getuid()) + ":" + str(os.getgid()),
                        str(output),
                        str(output / "assessment.json"),
                        str(output / "receipt.json"),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )


class RulesetAuditTests(unittest.TestCase):
    def setUp(self):
        self.rule = dict(
            id=1,
            name="protected main",
            target="branch",
            enforcement="active",
            conditions={"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            rules=[{"type": "merge_queue"}],
            updated_at="2026-10-21T10:00:00Z",
        )
        instant = datetime.now(timezone.utc)
        self.audit = dict(
            schema_version="github-ruleset-audit/v1",
            repository=s.g.REPOSITORY,
            repository_id=s.g.REPOSITORY_ID,
            audited_at=(instant - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            expires_at=s.settings()["binding"]["owner_grant_expires_at"],
            rulesets=[
                dict(
                    id=1,
                    bypass_disabled=True,
                    public_state_sha256=digest(s.ruleset_public_state(self.rule)),
                )
            ],
        )
        self.client = mock.Mock()
        self.client.errors = set()
        self.client.pages.return_value = [{"id": 1}]
        self.client.get.side_effect = lambda path: (
            [{"id": 1}] if path.endswith("/rulesets") else self.rule
        )

    def test_hidden_bypass_actors_require_exact_owner_audited_version(self):
        self.assertNotIn("bypass_actors", self.rule)
        s.verify_ruleset_audit(self.client, self.audit)
        self.rule["updated_at"] = "2026-10-21T10:00:01Z"
        with self.assertRaisesRegex(InputError, "audit_drift"):
            s.verify_ruleset_audit(self.client, self.audit)

    def test_new_ruleset_or_changed_rules_cannot_inherit_owner_assertion(self):
        self.client.pages.return_value = [{"id": 1}, {"id": 2}]
        self.client.get.side_effect = lambda path: (
            [{"id": 1}, {"id": 2}] if path.endswith("/rulesets") else self.rule
        )
        with self.assertRaises(InputError):
            s.verify_ruleset_audit(self.client, self.audit)
        self.client.get.side_effect = lambda path: (
            [{"id": 1}] if path.endswith("/rulesets") else self.rule
        )
        self.client.pages.return_value = [{"id": 1}]
        self.rule["rules"] = []
        with self.assertRaises(InputError):
            s.verify_ruleset_audit(self.client, self.audit)

    def test_expired_or_wrong_owner_audit_and_explicit_bypass_hold(self):
        original = self.audit["expires_at"]
        self.audit["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(InputError):
            s.verify_ruleset_audit(self.client, self.audit)
        self.audit["expires_at"] = original
        self.audit["repository"] = "other/repo"
        with self.assertRaises(InputError):
            s.verify_ruleset_audit(self.client, self.audit)
        self.audit["repository"] = s.g.REPOSITORY
        self.rule["bypass_actors"] = [{"actor_type": "Integration", "actor_id": 7}]
        with self.assertRaises(InputError):
            s.verify_ruleset_audit(self.client, self.audit)


if __name__ == "__main__":
    unittest.main()
