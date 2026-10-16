#!/usr/bin/env python3
"""Download one pinned public tool; never read or forward credentials."""

from pathlib import Path
import hashlib
import io
import json
import platform
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def install_cue() -> None:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise SystemExit("This pinned bootstrap supports Linux x86-64 only.")
    pin = json.loads((ROOT / "toolchain-lock.json").read_text())["cue"]
    if (ROOT / ".tools").is_symlink():
        raise SystemExit("Refusing a symlink tool directory.")
    destination = ROOT / ".tools" / "cue"
    if destination.is_symlink():
        raise SystemExit("Refusing a symlink executable.")
    if destination.exists() and pin.get("binary_sha256"):
        if hashlib.sha256(destination.read_bytes()).hexdigest() == pin["binary_sha256"]:
            print("Pinned CUE binary already installed.")
            return
    request = urllib.request.Request(
        pin["archive_url"], headers={"User-Agent": "gemara-local-spike"}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=60) as response:
        archive = response.read(50 * 1024 * 1024 + 1)
    if (
        len(archive) > 50 * 1024 * 1024
        or hashlib.sha256(archive).hexdigest() != pin["archive_sha256"]
    ):
        raise SystemExit("Tool archive failed its pinned size or digest check.")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        member = package.getmember("cue")
        if not member.isfile() or member.size > 100 * 1024 * 1024:
            raise SystemExit("Tool archive contains an unexpected executable entry.")
        stream = package.extractfile(member)
        if stream is None:
            raise SystemExit("Tool executable is absent.")
        binary = stream.read()
    digest = hashlib.sha256(binary).hexdigest()
    if pin.get("binary_sha256") and digest != pin["binary_sha256"]:
        raise SystemExit("Executable digest does not match the pin.")
    destination.parent.mkdir(exist_ok=True)
    if destination.is_symlink():
        raise SystemExit("Refusing to replace a symlink.")
    destination.write_bytes(binary)
    destination.chmod(0o755)
    print(
        "Installed checksum-verified CUE "
        + pin["version"]
        + "; binary sha256="
        + digest
    )


def install_schema():
    pin = json.loads((ROOT / "toolchain-lock.json").read_text())["gemara"]
    destination = ROOT / ".tools/schema"
    if destination.is_symlink():
        raise SystemExit("Refusing a symlink schema directory.")
    if destination.is_dir() and all(
        not (destination / name).is_symlink()
        and (destination / name).is_file()
        and hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
        for name, digest in pin["schema_files"].items()
    ):
        print("Pinned Gemara schemas already installed.")
        return
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(pin["archive_url"], timeout=45) as response:
        raw = response.read(5 * 1024 * 1024 + 1)
    if (
        len(raw) > 5 * 1024 * 1024
        or hashlib.sha256(raw).hexdigest() != pin["archive_sha256"]
    ):
        raise SystemExit("Schema archive failed digest/size verification.")
    destination.mkdir(exist_ok=True)
    found = set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive:
            parts = Path(member.name).parts
            if len(parts) != 2 or parts[-1] not in pin["schema_files"]:
                continue
            name = parts[-1]
            if name in found or not member.isfile() or member.size > 1024 * 1024:
                raise SystemExit("Unexpected schema archive entry.")
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != pin["schema_files"][name]:
                raise SystemExit("Schema digest mismatch.")
            target = destination / name
            if target.is_symlink():
                raise SystemExit("Refusing a symlink schema file.")
            target.write_bytes(data)
            found.add(name)
    if found != set(pin["schema_files"]):
        raise SystemExit("Schema archive is incomplete.")
    print("Installed pinned official Gemara schemas; no repository vendor tree.")


if __name__ == "__main__":
    install_cue()
    install_schema()
