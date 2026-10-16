#!/usr/bin/env python3
"""Build a repository-local Fullsend experiment without modifying its source repo."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent
SOURCE_COMMIT = "1528aac1b8361ef7f5cad1ba55f304402761580c"
OVERLAY = ROOT / "review-evidence-producer"


def overlay_digest():
    return hashlib.sha256(
        json.dumps(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(OVERLAY.iterdir())
                if p.suffix in {".go", ".txt"} or p.name == "go.mod"
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def build(source, offline=False):
    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    if tools.is_symlink():
        raise ValueError("symlink_tools")
    checkout = tools / "fullsend-evidence-source"
    if checkout.is_symlink():
        raise ValueError("symlink_source")
    if checkout.exists():
        shutil.rmtree(checkout)
    checkout.mkdir()
    clean = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", SOURCE_COMMIT],
        env=clean,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(checkout, filter="data")
    package = checkout / "internal/reviewevidence"
    package.mkdir()
    for path in OVERLAY.glob("*.go"):
        (package / path.name).write_bytes(path.read_bytes())
    (checkout / "internal/cli/review_evidence_lab.go").write_bytes(
        (OVERLAY / "fullsend-command.go.txt").read_bytes()
    )
    root = checkout / "internal/cli/root.go"
    text = root.read_text()
    needle = "\tcmd.AddCommand(newPostReviewCmd())"
    if text.count(needle) != 1:
        raise ValueError("unsupported_root_command")
    root.write_text(
        text.replace(needle, needle + "\n\tcmd.AddCommand(newReviewEvidenceLabCmd())")
    )
    cache = ROOT / ".tools/fullsend-build-cache"
    cache.mkdir(exist_ok=True)
    binary = ROOT.parent / ".fullsend/bin/fullsend"
    binary.parent.mkdir(exist_ok=True)
    if binary.is_symlink() or binary.parent.is_symlink():
        raise ValueError("symlink_binary")
    environment = dict(
        clean,
        HOME=str(cache),
        GOENV="off",
        GOTOOLCHAIN="local",
        GOTELEMETRY="off",
        GOWORK="off",
        GOPATH=str(cache / "gopath"),
        GOCACHE=str(cache / "cache"),
        GOPROXY="off" if offline else "https://proxy.golang.org",
        GOSUMDB="off" if offline else "sum.golang.org",
        CGO_ENABLED="0",
        GOFLAGS="-mod=readonly",
    )
    go = shutil.which("go")
    if not go:
        raise ValueError("go_required")
    for command in [
        [go, "test", "./internal/reviewevidence"],
        [
            go,
            "build",
            "-trimpath",
            "-buildvcs=false",
            "-ldflags=-s -w",
            "-o",
            str(binary),
            "./cmd/fullsend",
        ],
        [go, "mod", "verify"],
    ]:
        result = subprocess.run(
            command, cwd=checkout, env=environment, capture_output=True, timeout=600
        )
        if result.returncode:
            # Compiler output stays local; never upload it or copy environment data.
            (cache / "last-build-error.txt").write_bytes(result.stderr)
            raise ValueError("fullsend_build_failed")
    receipt = {
        "schema_version": "fullsend-evidence-build/v1",
        "source_commit": SOURCE_COMMIT,
        "overlay_sha256": overlay_digest(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_path": ".fullsend/bin/fullsend",
        "experiment_only": True,
        "signed": False,
        "default_review_install_changed": False,
    }
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out/fullsend-evidence-build.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Read-only local Fullsend Git checkout containing the pinned commit",
    )
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        build(args.source, args.offline)
    except Exception:
        raise SystemExit(
            "Fullsend evidence experiment build failed; see ignored local build diagnostics."
        )
