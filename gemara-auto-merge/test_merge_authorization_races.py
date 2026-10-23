from datetime import datetime, timedelta, timezone
import copy
import json
import os
import unittest
from unittest import mock

import authorize_auto_merge as p
from policy_evaluation import InputError, digest


class AuthorizationRaceTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            p.shared_gate, "verify_assessment", return_value={"decision": "eligible"}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.config = p.configuration()
        self.config["automatic_enabled"] = True
        self.config["automatic_pull_requests"]=[999001]
        self.config["automatic_expires_at"] = (datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        grant=mock.patch.object(p,"configuration",return_value=self.config);grant.start();self.addCleanup(grant.stop)
        selected={"decision":"eligible","configuration_sha256":"a"*64}
        gate=mock.patch.object(p.configured_policy,"evaluate",return_value=selected);gate.start();self.addCleanup(gate.stop)
        self.result = {
            "configured_policy": selected,
            "decision": "eligible",
            "stage": "enroll",
            "pull_request": 999001,
            "reviewed_head": "a" * 40,
            "base_sha": "b" * 40,
            "mode": "automatic",
            "configuration_sha256": digest(self.config),
        }
        self.pr = {
            "state": "open",
            "draft": False,
            "mergeable": True,
            "head": {"sha": "a" * 40, "repo": {"full_name": p.REPO}},
            "base": {"ref": "main", "repo": {"full_name": p.REPO}},
        }
        self.client = mock.MagicMock()
        self.client.errors = set()
        self.client.get.side_effect = lambda path: (
            self.pr if "/pulls/" in path else {"commit": {"sha": "b" * 40}}
        )

    def test_duplicate_events_request_queue_only_once(self):
        with (
            mock.patch.dict(
                os.environ,
                {
                    "PILOT_CAN_ENQUEUE": "true",
                    "PILOT_ENQUEUE_TOKEN": "test-installation-token",
                },
            ),
            mock.patch.object(p, "verify_scope"),
            mock.patch.object(p.g, "Client", return_value=self.client),
            mock.patch.object(p, "pending_queue_request", side_effect=[False, True]),
            mock.patch.object(
                p.subprocess, "run", return_value=mock.Mock(returncode=0)
            ) as writer,
        ):
            self.assertEqual(p.enqueue(self.result), "native_auto_merge_requested")
            self.assertEqual(
                p.enqueue(self.result), "native_auto_merge_already_requested"
            )
            self.assertEqual(writer.call_count, 1)

    def test_expiry_disablement_and_configuration_drift_refuse_before_action(self):
        for changes in [
            {"automatic_enabled": False},
            {"automatic_expires_at": "2020-01-01T00:00:00Z"},
        ]:
            config = dict(self.config, **changes)
            with (
                mock.patch.object(p, "configuration", return_value=config),
                self.assertRaises(InputError),
            ):
                p.pre_enqueue(
                    dict(self.result, configuration_sha256=digest(config)), self.client
                )
        with (
            mock.patch.object(
                p,
                "configuration",
                return_value=dict(self.config, automatic_enabled=False),
            ),
            self.assertRaises(InputError),
        ):
            p.pre_enqueue(self.result, self.client)

    def test_head_or_base_changed_after_evaluation_cannot_enqueue(self):
        self.pr["head"]["sha"] = "f" * 40
        with self.assertRaises(InputError):
            p.pre_enqueue(self.result, self.client)

        self.pr["head"]["sha"] = "a" * 40
        self.client.get.side_effect = lambda path: (
            self.pr if "/pulls/" in path else {"commit": {"sha": "f" * 40}}
        )
        with self.assertRaises(InputError):
            p.pre_enqueue(self.result, self.client)

    def test_maintenance_approval_is_rechecked_before_action(self):
        result = dict(
            self.result, mode="maintenance", maintenance_authorization={"approval": 1}
        )
        with (
            mock.patch.object(
                p, "maintenance_authorization", return_value=None
            ) as approval,
            self.assertRaises(InputError),
        ):
            p.pre_enqueue(result, self.client)
        approval.assert_called_once()

    def test_configuration_change_during_queue_lookup_is_not_ignored(self):
        with (
            mock.patch.object(
                p,
                "configuration",
                side_effect=[self.config, dict(self.config, automatic_enabled=False)],
            ),
            mock.patch.object(p, "pending_queue_request", return_value=False),
            self.assertRaises(InputError),
        ):
            p.pre_enqueue(self.result, self.client)

    def test_successful_graphql_with_partial_or_wrong_subject_data_is_not_enough(self):
        row = {
            "headRefOid": "a" * 40,
            "mergeQueueEntry": None,
            "autoMergeRequest": None,
        }

        def response(value):
            self.client.opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"data": {"repository": {"pullRequest": value}}}
            ).encode()

        response(row)
        self.assertFalse(p.pending_queue_request(self.client, 999001, "a" * 40))
        response(dict(row, mergeQueueEntry={"id": "entry"}))
        self.assertTrue(p.pending_queue_request(self.client, 999001, "a" * 40))
        for value in [
            {"headRefOid": "a" * 40},
            dict(row, headRefOid="f" * 40),
            dict(row, mergeQueueEntry=False),
        ]:
            response(value)
            with self.assertRaises(InputError):
                p.pending_queue_request(self.client, 999001, "a" * 40)

    def test_queue_composition_can_include_a_legitimate_new_base(self):
        old = {
            "code.py": ("blob", "100644", "a" * 40),
            p.DOCUMENT: ("blob", "100644", "b" * 40),
        }
        reviewed = dict(old, **{p.DOCUMENT: ("blob", "100644", "c" * 40)})
        new_base = dict(old, **{"code.py": ("blob", "100644", "d" * 40)})
        queue = dict(new_base, **{p.DOCUMENT: reviewed[p.DOCUMENT]})
        self.assertNotEqual(queue, reviewed)
        self.assertTrue(p.exact_tree(new_base, reviewed, queue))
        tampered = copy.deepcopy(queue)
        tampered["code.py"] = reviewed["code.py"]
        self.assertFalse(p.exact_tree(new_base, reviewed, tampered))
