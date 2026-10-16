#!/usr/bin/env python3
"""Render the official vendored layout locally; never call install APIs."""

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from build_fullsend_evidence_lab import ROOT, SOURCE_COMMIT, OVERLAY


def lock():
    repo = ROOT.parent
    paths = sorted(p for p in (repo / ".defaults").rglob("*") if p.is_file())
    paths += sorted((repo / ".github/workflows").glob("reusable-*.yml"))
    paths += [
        repo / name
        for name in [
            ".github/workflows/fullsend.yaml",
            ".fullsend/config.yaml",
            ".fullsend/harness/review-gemara.yaml",
            ".fullsend/scripts/post-review-gemara.py",
            ".fullsend/scripts/review-risk.patch",
            ".fullsend/scripts/publish-review-evidence.py",
            ".fullsend/vendor-manifest.yaml",
            ".fullsend/evidence-build.json",
            ".fullsend/bin/fullsend",
            "gemara-auto-merge/fullsend_review_evidence.py",
        ]
    ]
    blobs = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError("symlink_vendor_source")
        raw = path.read_bytes()
        blobs[str(path.relative_to(repo))] = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw
        ).hexdigest()
    (repo / ".fullsend/vendor-evidence-lock.json").write_text(
        json.dumps(
            {
                "schema_version": "vendored-review-host/v1",
                "source_commit": SOURCE_COMMIT,
                "host_files": [
                    {"path": name, "blob_sha1": value} for name, value in blobs.items()
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print("Pinned", len(blobs), "vendored host files; lock excludes its own digest.")


def install():
    source = ROOT / ".tools/fullsend-evidence-source"
    helper = source / "cmd/export-vendor-lab/main.go"
    helper.parent.mkdir(exist_ok=True)
    helper.write_bytes((OVERLAY / "export-vendor.go.txt").read_bytes())
    cache = ROOT / ".tools/fullsend-build-cache"
    go = shutil.which("go")
    env = {
        "PATH": str(Path(go).parent) + ":/usr/bin:/bin",
        "HOME": str(cache),
        "LANG": "C.UTF-8",
        "GOENV": "off",
        "GOTOOLCHAIN": "local",
        "GOTELEMETRY": "off",
        "GOWORK": "off",
        "GOPATH": str(cache / "gopath"),
        "GOCACHE": str(cache / "cache"),
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "CGO_ENABLED": "0",
    }
    child = subprocess.run(
        [
            go,
            "run",
            "-mod=readonly",
            "./cmd/export-vendor-lab",
            str(source),
            SOURCE_COMMIT,
        ],
        cwd=source,
        env=env,
        capture_output=True,
        timeout=180,
    )
    if child.returncode:
        raise ValueError("vendor_export_failed")
    for file in json.loads(child.stdout):
        name = file["Path"]
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("unsafe_vendor_path")
        path = ROOT.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError("symlink_vendor_path")
        path.write_bytes(base64.b64decode(file["Content"], validate=True))
        path.chmod(0o755 if file["Mode"] == "100755" else 0o644)
    receipt = json.loads((ROOT / "out/fullsend-evidence-build.json").read_text())
    (ROOT.parent / ".fullsend/evidence-build.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    patch_review_wrapper()
    print("Official vendored runtime rendered with pinned upstream Review wrapper.")


def patch_review_wrapper():
    """Preserve supported OIDC identity; keep runtime and publication local."""
    shim = ROOT.parent / ".github/workflows/fullsend.yaml"
    text = shim.read_text()
    local = "uses: ./.github/workflows/reusable-dispatch.yml"
    upstream = (
        "uses: fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@"
        + SOURCE_COMMIT
    )
    assert local in text or upstream in text
    shim.write_text(text.replace(local, upstream))
    action = ROOT.parent / ".defaults/action.yml"
    text = action.read_text()
    marker = "    - name: Upload fullsend artifacts\n"
    upload = """    - name: Retain native Fullsend Review evidence
      if: always() && inputs.agent == 'review'
      uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9
      with:
        name: fullsend-review-evidence-${{ github.run_attempt }}
        path: ${{ github.workspace }}/output/fullsend-review-evidence.json
        if-no-files-found: ignore
        retention-days: 14

"""
    if "    - name: Retain native Fullsend Review evidence\n" not in text:
        assert text.count(marker) == 1
        action.write_text(text.replace(marker, upload + marker))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--lock"]:
        lock()
    else:
        install()
