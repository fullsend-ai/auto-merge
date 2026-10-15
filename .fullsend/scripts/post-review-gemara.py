#!/usr/bin/env python3
"""Pinned official Review post-script plus this lab's revision-bound risk receipt."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

UPSTREAM = "https://raw.githubusercontent.com/fullsend-ai/agents/a159f388364279487818325ef5d3cc1bcd31e1ea/scripts/post-review.sh"
SOURCE_SHA256 = "f07fb6081a7164abe8c2f219aa034ea72a5c9009da1f106bd2d8f65dcc26a077"
PATCH_SHA256 = "ccfdf981a575ae4c86018d8791f24f244545cb634424000bda214c8cdc13e909"
RESULT_SHA256 = "74e1f153f70252a099f9537d7fdc15b2438ff2c8f8d39b69f3f188ae10798961"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect_refused")


def fetch():
    # No forge token, proxy credentials or user-controlled URL enters this request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(UPSTREAM, timeout=30) as response:
        source = response.read(256 * 1024 + 1)
    if len(source) > 256 * 1024:
        raise ValueError("source_too_large")
    return source


def prepare(directory, source, patch):
    for data, expected in [(source, SOURCE_SHA256), (patch, PATCH_SHA256)]:
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("pin_mismatch")
    script = directory / "scripts/post-review.sh"
    script.parent.mkdir(mode=0o700)
    script.write_bytes(source)
    patch_file = directory / "risk.patch"
    patch_file.write_bytes(patch)
    clean = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(directory),
        "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    result = subprocess.run(
        ["/usr/bin/git", "apply", "--", str(patch_file)],
        cwd=directory,
        env=clean,
        capture_output=True,
        timeout=15,
    )
    if (
        result.returncode
        or hashlib.sha256(script.read_bytes()).hexdigest() != RESULT_SHA256
    ):
        raise ValueError("patched_source_mismatch")
    return script


def main():
    try:
        patch = Path(__file__).with_name("review-risk.patch").read_bytes()
        with tempfile.TemporaryDirectory(
            prefix="fullsend-review-receipt-"
        ) as temporary:
            script = prepare(Path(temporary), fetch(), patch)
            print(
                "Using pinned official Review post-script with lab risk receipt extension.",
                flush=True,
            )
            # The original host post-script needs its existing role credentials.
            # No additional credentials or sandbox/network permissions are added.
            return subprocess.run(
                ["/usr/bin/bash", str(script)], env=os.environ.copy()
            ).returncode
    except Exception:
        print(
            "Review receipt setup failed; no fallback to unverified code.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
