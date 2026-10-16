#!/usr/bin/env python3
"""Validate artifacts against hash-pinned official schemas using a clean process."""

from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
DEFINITIONS = {
    "ControlCatalog": "#ControlCatalog",
    "Policy": "#Policy",
    "EvaluationLog": "#EvaluationLog",
}


class ValidationError(ValueError):
    pass


def verify_tools() -> tuple[Path, list[Path]]:
    lock = json.loads((ROOT / "toolchain-lock.json").read_text())
    vendor = ROOT / ".tools" / "schema"
    for name, expected in lock["gemara"]["schema_files"].items():
        path = vendor / name
        if (
            path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValidationError("schema_pin_mismatch")
    binary = ROOT / ".tools" / "cue"
    if not binary.is_file() or binary.is_symlink():
        raise ValidationError("pinned_validator_not_installed")
    if hashlib.sha256(binary.read_bytes()).hexdigest() != lock["cue"]["binary_sha256"]:
        raise ValidationError("validator_pin_mismatch")
    paths = sorted(vendor.glob("*.cue"))
    if set(p.name for p in paths) != {
        n for n in lock["gemara"]["schema_files"] if "/" not in n and n.endswith(".cue")
    }:
        raise ValidationError("unexpected_schema_file")
    return binary, paths


def validate(data: dict, artifact: str) -> None:
    if artifact not in DEFINITIONS:
        raise ValidationError("unsupported_artifact")
    binary, schemas = verify_tools()
    with tempfile.TemporaryDirectory(prefix="gemara-validate-") as directory:
        source = Path(directory) / "artifact.json"
        source.write_text(json.dumps(data, allow_nan=False))
        try:
            result = subprocess.run(
                [
                    str(binary),
                    "vet",
                    "-c",
                    "-d",
                    DEFINITIONS[artifact],
                    *map(str, schemas),
                    str(source),
                ],
                cwd=ROOT,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValidationError("validator_unavailable") from exc
        if result.returncode:
            # CUE diagnostics can contain input text or local paths: never emit them.
            raise ValidationError("official_schema_rejected_" + artifact)
