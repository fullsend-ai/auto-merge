#!/usr/bin/env python3
"""Bounded public-content checks; reports file names, never matched content."""

from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = "c06d5b8ba0f1be703ed83415986c179d97f3329c"
PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"github_pat_[A-Za-z0-9_]{30,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
    r"\bsk-[A-Za-z0-9_-]{30,}",
    r"AKIA[A-Z0-9]{16}",
    r"/home/[A-Za-z0-9_-]+/",
    r"redhat\.atlassian\.net",
    r"gitlab\.cee\.redhat\.com",
    r"file://",
]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    # The platform experiment explicitly disables both legacy entry points and
    # adds one reviewed, unprivileged fixture-only workflow. All other execution
    # and safety files remain protected against accidental scope expansion.
    permitted = {
        ".fullsend/config.yaml": git("show", BASE + ":.fullsend/config.yaml").replace(
            "    - name: auto-merge\n", "    - name: auto-merge\n      enabled: false\n"
        ),
        ".github/workflows/auto-merge-context.yml": git(
            "show", BASE + ":.github/workflows/auto-merge-context.yml"
        ).replace(
            "      github.event.issue.pull_request\n",
            "      false\n      && github.event.issue.pull_request\n",
            1,
        ),
    }
    for name, expected in permitted.items():
        if (ROOT / name).read_text().rstrip() != expected.rstrip():
            raise SystemExit(
                "Legacy disabling diff does not match the reviewed boundary."
            )
    workflow = ".github/workflows/autonomy-fixtures.yml"
    if (
        hashlib.sha256((ROOT / workflow).read_bytes()).hexdigest()
        != "a503d3187a72fcd4a3aa618c1777b698132e2bec246611d5dfa51a357188e513"
    ):
        raise SystemExit("Fixture workflow differs from its reviewed pin.")
    allowed = set(permitted) | {workflow}
    if any(
        name.startswith((".github/", ".fullsend/", "tests/"))
        or name in {"docs/AUTO-MERGE-SECURITY-CONTRACT.md", "docs/example-feature.md"}
        for name in changed - allowed
    ):
        raise SystemExit("Attempt 1 execution or safety files changed.")
    remaining = (
        set(
            git(
                "diff",
                "--name-only",
                BASE,
                "--",
                ".github",
                ".fullsend",
                "docs/AUTO-MERGE-SECURITY-CONTRACT.md",
                "tests",
                "docs/example-feature.md",
            ).splitlines()
        )
        - allowed
    )
    if remaining:
        raise SystemExit("Attempt 1 execution or safety files changed.")
    problems = []
    for name in sorted(changed):
        p = ROOT / name
        if p.is_symlink() or not p.is_file():
            problems.append(name)
            continue
        if (
            p.suffix in {".pyc", ".mp4", ".mp3", ".env"}
            or ".tools" in p.parts
            or p.name.startswith(".env")
        ):
            problems.append(name)
            continue
        if p.resolve() == Path(__file__).resolve():
            continue  # The detector deliberately contains its own detection strings.
        try:
            text = p.read_text()
        except (UnicodeError, OSError):
            problems.append(name)
            continue
        if any(re.search(pattern, text) for pattern in PATTERNS):
            problems.append(name)
    baseline = json.loads(
        (ROOT / "docs/attempts/01-agent-led/baseline.json").read_text()
    )
    for name, expected in baseline["documents"].items():
        original = subprocess.run(
            ["git", "show", BASE + ":" + name],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        if hashlib.sha256(original).hexdigest() != expected:
            raise SystemExit("Attempt 1 document baseline mismatch.")
    if problems:
        print(json.dumps({"public_check": "failed", "files": problems}))
        return 1
    print(
        json.dumps(
            {
                "public_check": "passed",
                "changed_files_checked": len(changed),
                "legacy_scripts_unchanged": True,
                "legacy_entry_points_disabled_in_local_diff": True,
                "new_workflow": "pinned fixture-only contents:read; no secrets or credential persistence",
                "scope": "pattern and file-boundary checks; not a comprehensive secret audit",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
