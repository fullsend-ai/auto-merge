#!/usr/bin/env python3
"""Exercise Fullsend's native vendor collectors against an approved source snapshot."""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
REVISION = "f5934f595239c5c9bb589f9d8e6a3f30a58945d8"


def prepare(source):
    source = source.resolve()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=source, capture_output=True, text=True, check=True
        ).stdout.strip()

    if git("rev-parse", "HEAD") != REVISION or git("status", "--porcelain"):
        raise SystemExit("Vendor probe requires the clean approved Fullsend commit.")
    go = shutil.which("go")
    if not go:
        raise SystemExit("Go is required.")
    out = ROOT / "out"
    if out.is_symlink():
        raise SystemExit("Refusing a symlink output directory.")
    destination = out / (
        "vendor-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    destination.mkdir(parents=True, exist_ok=False)
    cache = Path(tempfile.gettempdir()) / "autonomy-build-cache"
    env = {
        "PATH": str(Path(go).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "GOENV": "off",
        "GOTOOLCHAIN": "local",
        "GOTELEMETRY": "off",
        "GOPATH": str(cache / "gopath"),
        "GOCACHE": str(cache / "cache"),
        "GOPROXY": "https://proxy.golang.org",
        "GOSUMDB": "sum.golang.org",
        "CGO_ENABLED": "0",
    }
    with tempfile.TemporaryDirectory(prefix="autonomy-vendor-probe-") as tmp:
        module = Path(tmp)
        # The temporary import path is within Fullsend's permitted internal namespace.
        (module / "go.mod").write_text(
            "module github.com/fullsend-ai/fullsend/spike-vendor-probe\n\ngo 1.26.5\n\nrequire github.com/fullsend-ai/fullsend v0.0.0\n\nreplace github.com/fullsend-ai/fullsend => "
            + str(source)
            + "\nreplace github.com/fullsend-ai/fullsend/internal/mintcore => "
            + str(source / "internal/mintcore")
            + "\n"
        )
        shutil.copyfile(ROOT / "vendorprobe/main.go", module / "main.go")
        for args in [
            [go, "mod", "tidy"],
            [go, "run", "-mod=readonly", ".", str(source), str(destination), REVISION],
        ]:
            result = subprocess.run(
                args, cwd=module, env=env, capture_output=True, timeout=180
            )
            if result.returncode:
                raise SystemExit(
                    "Native vendor preparation failed; no captured diagnostics published."
                )
    print(
        "Native Fullsend vendor content and routing comparison passed. No installer or workflow ran."
    )
    print("Local output: " + str(destination.relative_to(ROOT)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fullsend-source", type=Path, required=True)
    prepare(parser.parse_args().fullsend_source)
