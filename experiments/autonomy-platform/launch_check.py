#!/usr/bin/env python3
"""Read-only comparison of trusted main with this reviewed setup; no activation."""

import base64
import hashlib
import json

from github_observe import Client, REPOSITORY
from platform_lab import ROOT, require


def inspect(client=None):
    client = client or Client()
    repo = ROOT.parents[1]
    prefix = "repos/" + REPOSITORY + "/"
    commit = client.get(prefix + "commits/main")
    require(commit is not None, "main_unavailable")
    revision = commit["sha"]
    require(
        len(revision) == 40 and all(c in "0123456789abcdef" for c in revision),
        "invalid_revision",
    )
    expected = [
        ".fullsend/config.yaml",
        ".github/workflows/auto-merge-context.yml",
        ".github/workflows/autonomy-fixtures.yml",
    ]
    matches = {}
    for name in expected:
        entry = client.get(prefix + "contents/" + name + "?ref=" + revision)
        match = False
        if (
            entry
            and entry.get("encoding") == "base64"
            and isinstance(entry.get("content"), str)
            and len(entry["content"]) < 100000
        ):
            try:
                raw = base64.b64decode(
                    entry["content"].replace("\n", ""), validate=True
                )
                match = (
                    hashlib.sha256(raw).digest()
                    == hashlib.sha256((repo / name).read_bytes()).digest()
                )
            except ValueError:
                pass
        matches[name] = match
    return {
        "repository": REPOSITORY,
        "main_sha": revision,
        "trusted_setup_matches_local": all(matches.values()),
        "file_matches": matches,
        "api_errors": sorted(client.errors),
        "writes_performed": False,
        "activation_permitted": False,
        "note": "A match is a setup precondition only; it does not grant workflow or merge authority.",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit("launch_check_failed_closed")
