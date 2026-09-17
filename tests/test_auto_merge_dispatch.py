#!/usr/bin/env python3
"""Exercise the custom Auto-Merge harness against normalized CEL events."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / ".fullsend"
FULLSEND = shutil.which("fullsend")


def event(transition: dict, *, entity_kind: str = "change_proposal") -> dict:
    entity = {"kind": entity_kind, "id": 5, "url": "https://github.com/ascerra/auto-merge/pull/5"}
    if entity_kind == "work_item":
        entity["linked_change_proposal"] = {"id": 5, "url": "https://github.com/ascerra/auto-merge/pull/5"}
    return {
        "repo": "ascerra/auto-merge",
        "entity": entity,
        "transition": transition,
        "actor": {"id": "alice", "kind": "human", "role": "write", "is_entity_author": False},
        "state": {
            "labels": [],
            "change_proposal": {
                "id": 5,
                "head_repo": "ascerra/auto-merge",
                "base_repo": "ascerra/auto-merge",
                "head_ref": "agent/test",
                "base_ref": "main",
                "head_sha": "a" * 40,
                "author_id": "fullsend-ai-coder[bot]",
                "is_fork": False,
            },
        },
        "source": {"system": "github", "raw_type": "test", "raw_action": "test"},
    }


def dispatch(payload: dict) -> list[dict]:
    if FULLSEND is None:
        raise unittest.SkipTest("fullsend CLI is not installed")
    result = subprocess.run(
        [FULLSEND, "dispatch", "--config-dir", str(CONFIG_DIR), "--input-driver", "json", "--input-file", "-", "--output-driver", "json", "--repo", "ascerra/auto-merge"],
        input=json.dumps(payload), text=True, capture_output=True, check=True, cwd=ROOT,
    )
    return json.loads(result.stdout) or []


@unittest.skipUnless(FULLSEND, "fullsend CLI is not installed")
class AutoMergeDispatchTests(unittest.TestCase):
    def assert_selected(self, payload: dict) -> None:
        selected = dispatch(payload)
        self.assertEqual(len(selected), 1, selected)
        self.assertEqual(selected[0]["agent"], "auto-merge")
        self.assertEqual(selected[0]["role"], "coder")

    def test_manual_command_selects_agent(self) -> None:
        self.assert_selected(event({"kind": "comment_added", "comment": {"command": "/fs-auto-merge", "body": "/fs-auto-merge", "instruction": ""}}, entity_kind="work_item"))

    def test_approved_review_selects_agent(self) -> None:
        self.assert_selected(event({"kind": "review_submitted", "review": {"state": "approved", "reviewer_id": "reviewer"}}))

    def test_readiness_label_selects_agent(self) -> None:
        self.assert_selected(event({"kind": "label_changed", "label": {"name": "fullsend-auto-merge-ready", "action": "added"}}))

    def test_readiness_label_on_work_item_selects_agent(self) -> None:
        self.assert_selected(event({"kind": "label_changed", "label": {"name": "fullsend-auto-merge-ready", "action": "added"}}, entity_kind="work_item"))

    def test_unrelated_label_does_not_select_agent(self) -> None:
        self.assertEqual(dispatch(event({"kind": "label_changed", "label": {"name": "hold", "action": "added"}})), [])

    def test_rejected_review_does_not_select_agent(self) -> None:
        self.assertEqual(dispatch(event({"kind": "review_submitted", "review": {"state": "changes_requested", "reviewer_id": "reviewer"}})), [])


if __name__ == "__main__":
    unittest.main()
