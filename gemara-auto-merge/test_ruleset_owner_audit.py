"""Owner publication must refuse unsafe state before changing the environment variable."""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

from policy_evaluation import InputError, ROOT


class OwnerAuditTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "owner_audit", ROOT.parent / "scripts/publish_ruleset_audit.py"
        )
        self.owner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.owner)
        self.admin = True
        self.actors = []
        self.pattern = "main"
        self.published = None
        self.rule = dict(
            id=1,
            name="protected main",
            target="branch",
            enforcement="active",
            conditions={},
            rules=[{"type": "merge_queue"}],
            updated_at="2026-10-20T00:00:00Z",
            bypass_actors=self.actors,
        )

        def api(path):
            if path == "repos/" + self.owner.REPO:
                return {"permissions": {"admin": self.admin}}
            if "/rulesets?" in path:
                return [{"id": 1}]
            if path.endswith("/rulesets/1"):
                return self.rule
            if path.endswith("/deployment-branch-policies"):
                return {"branch_policies": [{"name": self.pattern, "type": "branch"}]}
            return {
                "deployment_branch_policy": {
                    "protected_branches": False,
                    "custom_branch_policies": True,
                }
            }

        self.api = api

        def command(args, **kwargs):
            if args[2] == "set":
                self.published = json.loads(kwargs["input"])
                return mock.Mock(returncode=0, stdout="")
            return mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    [
                        {
                            "name": "GEMARA_RULESET_AUDIT",
                            "value": json.dumps(self.published),
                        }
                    ]
                ),
            )

        self.command = command

    def run_audit(self):
        with mock.patch.object(
            self.owner, "api", side_effect=self.api
        ), mock.patch.object(self.owner.subprocess, "run", side_effect=self.command):
            self.owner.audit()

    def test_owner_publishes_only_version_data_and_preserves_expiry(self):
        self.run_audit()
        self.assertTrue(self.published["rulesets"][0]["bypass_disabled"])
        self.assertEqual(
            self.published["expires_at"],
            self.owner.settings()["binding"]["owner_grant_expires_at"],
        )
        self.assertNotIn("bypass_actors", json.dumps(self.published))

    def test_non_admin_or_active_bypass_cannot_publish(self):
        self.admin = False
        with self.assertRaises(InputError):
            self.run_audit()
        self.assertIsNone(self.published)
        self.admin = True
        self.actors.append({"actor_type": "Integration", "actor_id": 7})
        with self.assertRaises(InputError):
            self.run_audit()
        self.assertIsNone(self.published)

    def test_hidden_actor_list_does_not_become_empty_owner_assertion(self):
        self.rule.pop("bypass_actors")
        with self.assertRaises(InputError):
            self.run_audit()
        self.assertIsNone(self.published)

    def test_environment_must_allow_only_main(self):
        self.pattern = "*"
        with self.assertRaises(InputError):
            self.run_audit()
        self.assertIsNone(self.published)
