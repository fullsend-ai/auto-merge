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


def main() -> None:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise SystemExit("This pinned bootstrap supports Linux x86-64 only.")
    pin = json.loads((ROOT / "tool-lock.json").read_text())["cue"]
    destination = ROOT / ".tools" / "cue"
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


if __name__ == "__main__":
    main()
