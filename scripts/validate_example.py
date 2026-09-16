#!/usr/bin/env python3
"""Validate the deterministic documentation fixture used by the E2E test."""

from pathlib import Path
import re
import sys


DOCUMENT = Path("docs/example-feature.md")
REQUIRED_LINES = (
    "# Example feature",
    "Status: ready",
    "## Why",
    "## Behavior",
    "## Verification",
)
FORBIDDEN_PATTERNS = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{16,}\b"),
)


def main() -> int:
    if not DOCUMENT.is_file():
        print(f"missing required exercise document: {DOCUMENT}", file=sys.stderr)
        return 1

    text = DOCUMENT.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    if not lines or lines[0] != REQUIRED_LINES[0]:
        errors.append(f"first line must be exactly: {REQUIRED_LINES[0]}")

    for required in REQUIRED_LINES[1:]:
        if required not in lines:
            errors.append(f"missing required line: {required}")

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            errors.append(f"forbidden content matched: {pattern.pattern}")

    if errors:
        print("example document validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"validated {DOCUMENT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

