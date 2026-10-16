"""Exercise the real skill examples with fixture API responses; no network."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / ".fullsend/skills/github/SKILL.md"
BLOCKS = re.findall(r"```bash\n(.*?)```", SKILL.read_text(), re.S)


class SkillShellCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = self.bin / "gh"
        stub.write_text(
            "#!" + sys.executable + "\n"
            "import json,os,sys\n"
            "from pathlib import Path\n"
            "data=json.loads(Path(os.environ['FIXTURE']).read_text())\n"
            "endpoint=next(x for x in sys.argv if x.startswith('repos/'))\n"
            "key='compare' if '/compare/' in endpoint else 'commits' if '/commits?' in endpoint else 'files' if '/files?' in endpoint else 'pr'\n"
            "if key in ['files','commits'] and not all(x in sys.argv for x in ['--paginate','--slurp']): sys.exit(9)\n"
            "if data.get('failure')==key: sys.exit(7)\n"
            "print(json.dumps(data[key]))\n"
        )
        stub.chmod(0o755)
        self.data = {
            "pr": {"head": {"sha": "a" * 40}, "draft": False, "commits": 2},
            "files": [
                [{"filename": "docs/a.md", "additions": 1, "deletions": 0}],
                [{"filename": "docs/b.md", "additions": 2, "deletions": 1}],
            ],
            "commits": [
                [{"commit": {"message": "first"}}],
                [{"commit": {"message": "second"}}],
            ],
            "compare": {
                "status": "ahead",
                "behind_by": 0,
                "total_commits": 1,
                "files": [
                    {
                        "filename": "docs/a.md",
                        "status": "modified",
                        "patch": "@@ -1 +1 @@\n-old\n+new",
                    }
                ],
            },
        }
        (self.root / "pr-diff.txt").write_text("FULL PR DIFF\n")

    def run_block(self, index):
        fixture = self.root / "fixture.json"
        fixture.write_text(json.dumps(self.data))
        env = {
            "PATH": str(self.bin) + os.pathsep + os.defpath,
            "HOME": str(self.root),
            "BASH_ENV": "/dev/null",
            "FIXTURE": str(fixture),
            "REPO_FULL_NAME": "fullsend-ai/auto-merge",
            "PR_NUMBER": "43",
            "HEAD_SHA": "a" * 40,
            "PRIOR_REVIEW_SHA": "b" * 40,
        }
        return subprocess.run(
            ["bash", "-c", BLOCKS[index].replace("/sandbox/workspace", str(self.root))],
            env=env,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_metadata_preserves_pagination_and_rejects_invalid_counts(self):
        for count, expected in [
            (2, "2"),
            ("001", "001"),
            (None, "unknown"),
            (-1, "unknown"),
            ("2\n3", "unknown"),
        ]:
            with self.subTest(count=count):
                self.data["pr"]["commits"] = count
                self.assertEqual(self.run_block(0).returncode, 0)
                self.assertEqual(
                    (self.root / "pr-commit-count").read_text().strip(), expected
                )
                self.assertEqual(
                    len(json.loads((self.root / "pr-files.json").read_text())), 2
                )
        self.data["failure"] = "files"
        self.assertNotEqual(self.run_block(0).returncode, 0)

    def test_commit_messages_keep_cap_and_unavailable_signals(self):
        for count, incomplete in [(2, "false"), (251, "true"), ("unknown", "true")]:
            (self.root / "pr-commit-count").write_text(str(count) + "\n")
            self.assertEqual(self.run_block(5).returncode, 0)
            self.assertEqual(
                (self.root / "pr-commit-messages-available").read_text().strip(), "true"
            )
            self.assertEqual(
                (self.root / "pr-commit-messages-incomplete").read_text().strip(),
                incomplete,
            )
        self.data["failure"] = "commits"
        self.run_block(5)
        self.assertEqual(
            (self.root / "pr-commit-messages-available").read_text().strip(), "false"
        )

    def test_incomplete_or_failed_compare_retains_full_diff(self):
        self.assertEqual(self.run_block(6).returncode, 0)
        self.assertEqual(
            (self.root / "pr-compare-incomplete").read_text().strip(), "false"
        )
        self.data["compare"]["files"] *= 300
        self.assertEqual(self.run_block(6).returncode, 0)
        self.assertEqual(
            (self.root / "pr-compare-incomplete").read_text().strip(), "true"
        )
        self.assertEqual(
            (self.root / "pr-incremental-diff.txt").read_text(), "FULL PR DIFF\n"
        )
        self.data["failure"] = "compare"
        self.run_block(6)
        self.assertEqual(
            (self.root / "pr-changed-files.txt").read_text().strip(), "all"
        )
