import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import configured_policy as c
from policy_evaluation import InputError

HEAD="a"*40
BASE="b"*40
NOW="2026-10-23T12:00:00Z"

class Client:
    def __init__(self, checks=None, statuses=None):
        self.checks=[] if checks is None else checks
        self.statuses=[] if statuses is None else statuses
        self.errors=set()
    def pages(self,path,key=None):
        return self.checks if key=="check_runs" else self.statuses

def check(n=1,conclusion="success",status="completed",name="Required test"):
    return dict(id=n,head_sha=HEAD,app={"id":15368},name=name,status=status,conclusion=conclusion)

class UpstreamChecksTests(unittest.TestCase):
    def run_policy(self,client,mode="enforce"):
        with mock.patch.object(c,"configuration",return_value={"mode":mode,"policy":"fullsend-default","controls":[c.CONTROL]}):
            return c.evaluate(client,HEAD,BASE,NOW)

    def test_real_upstream_control_passes_through_native_gemara(self):
        r=self.run_policy(Client([check()]))
        self.assertEqual(r["decision"],"eligible")
        self.assertEqual(r["assessments"][0]["requirement"],c.CONTROL)
        self.assertEqual(r["evaluation"]["engine"],"gemara")
        self.assertFalse(r["mutation_permitted"])

    def test_optional_failure_holds_when_required_checks_pass(self):
        r=self.run_policy(Client([check(),check(2,"failure",name="Optional test")]))
        self.assertEqual(r["decision"],"hold")
        self.assertEqual(r["assessments"][0]["state"],"failed")

    def test_pending_cancelled_and_missing_hold(self):
        for rows in [[],[check(status="in_progress",conclusion=None)],[check(conclusion="cancelled")],[check(conclusion="timed_out")]]:
            self.assertEqual(self.run_policy(Client(rows))["decision"],"hold")

    def test_status_context_failure_and_rerun(self):
        statuses=[dict(id=1,context="external-ci",state="failure")]
        self.assertEqual(self.run_policy(Client([check()],statuses))["decision"],"hold")
        statuses.append(dict(id=2,context="external-ci",state="success"))
        self.assertEqual(self.run_policy(Client([check()],statuses))["decision"],"eligible")
        self.assertEqual(self.run_policy(Client([check(1,"failure"),check(2)]))["decision"],"eligible")

    def test_partial_api_wrong_head_and_malformed_hold_unknown(self):
        bad=check();bad["head_sha"]=BASE
        for client in [Client([bad]),Client([dict(check(),id="wrong")]),Client([check()],[{}])]:
            self.assertEqual(self.run_policy(client)["assessments"][0]["state"],"unknown")
        client=Client([check()]);client.errors.add("api_error")
        self.assertEqual(self.run_policy(client)["decision"],"hold")

    def test_shadow_evaluates_without_write_and_off_collects_nothing(self):
        r=self.run_policy(Client([check()]),"shadow")
        self.assertTrue(r["would_allow"]);self.assertEqual(r["decision"],"hold")
        with mock.patch.object(c,"checks_value",side_effect=AssertionError("must not read")):
            self.assertEqual(self.run_policy(Client(),"off")["reason"],"mode_off")

    def test_neutral_and_skipped_do_not_hide_failure(self):
        self.assertEqual(self.run_policy(Client([check(1,"failure"),check(2,"skipped")]))["decision"],"hold")
        self.assertEqual(self.run_policy(Client([check(),check(2,"neutral",name="Notice")]))["decision"],"eligible")
        self.assertEqual(self.run_policy(Client([check(1,"failure"),check(2,"skipped",name="Skipped")]))["decision"],"hold")

    def test_binary_and_source_integrity(self):
        cfg=c.configuration();self.assertEqual(cfg["mode"],"shadow")
        with mock.patch.object(c,"load",return_value={"binary_sha256":"0"*64}):
            with self.assertRaises(InputError):c.configuration()
        with mock.patch.object(c,"load",return_value={"commit":"wrong"}):
            with self.assertRaises(InputError):c.upstream_bundle()

    def test_queue_checks_bind_merged_revision_and_exclude_only_current_assessment(self):
        rows=[check(),dict(check(2,None,"in_progress","Policy assessment"),check_suite={"id":9})]
        client=Client(rows)
        client.get=lambda _:dict(path=".github/workflows/gemara-merge-queue.yml",event="merge_group",head_sha=HEAD,check_suite_id=9)
        with mock.patch.dict("os.environ",{"GITHUB_RUN_ID":"123"}):
            self.assertTrue(c.checks_value(client,HEAD,"queue")[0])
            rows.append(dict(check(3,"failure",name="Other suite"),check_suite={"id":10}))
            self.assertFalse(c.checks_value(client,HEAD,"queue")[0])
            client.get=lambda _:dict(path="untrusted",event="merge_group",head_sha=HEAD,check_suite_id=9)
            self.assertIsNone(c.checks_value(client,HEAD,"queue")[0])

    def test_final_writer_rechecks_configuration_and_check_outcome(self):
        import authorize_auto_merge as pilot
        prior={"decision":"eligible","configuration_sha256":"a"*64}
        result={"reviewed_head":HEAD,"base_sha":BASE,"configured_policy":prior}
        with mock.patch.object(pilot,"configuration",return_value={}),mock.patch.object(c,"evaluate",return_value={**prior,"decision":"hold"}):
            with self.assertRaises(InputError):pilot.pre_enqueue(result,Client())
        with mock.patch.object(pilot,"configuration",return_value={}),mock.patch.object(c,"evaluate",return_value={**prior,"configuration_sha256":"b"*64}):
            with self.assertRaises(InputError):pilot.pre_enqueue(result,Client())
