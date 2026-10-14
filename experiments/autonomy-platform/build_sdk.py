#!/usr/bin/env python3
"""Build the pinned module with no inherited credentials or automatic toolchain."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
SDK = ROOT / "sdk"


def build(offline=False):
    go = shutil.which("go")
    if not go:
        raise SystemExit("Go 1.25 or newer is required.")
    cache = Path(tempfile.gettempdir()) / "autonomy-build-cache"
    cache.mkdir(exist_ok=True)
    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    if tools.is_symlink():
        raise SystemExit("Refusing a symlink tool directory.")
    destination = tools / "gemara-adapter"
    if destination.is_symlink():
        raise SystemExit("Refusing a symlink executable.")
    env = {
        "PATH": str(Path(go).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "GOENV": "off",
        "GOTOOLCHAIN": "local",
        "GOTELEMETRY": "off",
        "GOPATH": str(cache / "gopath"),
        "GOCACHE": str(cache / "cache"),
        "GOPROXY": "off" if offline else "https://proxy.golang.org",
        "GOSUMDB": "off" if offline else "sum.golang.org",
        "CGO_ENABLED": "0",
    }
    for command in [
        [go, "mod", "verify"],
        [go, "test", "-mod=readonly", "./..."],
        [
            go,
            "build",
            "-mod=readonly",
            "-trimpath",
            "-buildvcs=false",
            "-o",
            str(destination),
            ".",
        ],
    ]:
        result = subprocess.run(
            command, cwd=SDK, env=env, capture_output=True, timeout=180
        )
        if result.returncode:
            raise SystemExit(
                "Pinned SDK build failed; no captured diagnostics were published."
            )
    lock = {
        "sdk_commit": "5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2",
        "sdk_module": "v0.11.1-0.20261009030221-5e33fda460a8",
        "sdk_schema_version": "v1.5.0",
        "output_schema_version": "v1.6.0",
        "adapter_binary_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "adapter_sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [SDK / "main.go", SDK / "go.mod", SDK / "go.sum"]
        },
    }
    (ROOT / "build-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(
        "Pinned Gemara SDK adapter built; module hashes verified; clean build environment."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    build(parser.parse_args().offline)
