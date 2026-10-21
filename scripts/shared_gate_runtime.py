#!/usr/bin/env python3
"""Pinned shared-code preparation, read-only quality collection and isolated assessment."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

from run_shared_review import bounded, jail_prefix, PROBE_SOURCE, require, run

GO = "/opt/hostedtoolcache/go/1.26.9/x64/bin/go"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prepare(config, output):
    pin = config["tool"]
    require(
        pin["module"] == "github.com/ascerra/fullsend-gemara-integration"
        and pin["package"] == pin["module"] + "/cmd/gemara-owner"
        and pin["go_version"] == "1.26.9",
        "invalid_shared_pin",
    )
    out = Path(output)
    out.mkdir(mode=0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(out.resolve()),
        "GOPATH": str(out.resolve() / "gopath"),
        "GOCACHE": str(out.resolve() / "cache"),
        "GOBIN": str(out.resolve() / "bin"),
        "GOTOOLCHAIN": "local",
        "GOTELEMETRY": "off",
        "CGO_ENABLED": "0",
        "GOPROXY": "https://proxy.golang.org",
        "GOSUMDB": "sum.golang.org",
    }
    metadata = out / "module.json"
    run(
        [GO, "mod", "download", "-json", pin["module"] + "@" + pin["version"]],
        env=env,
        cwd=out,
        output=metadata,
    )
    module = bounded(metadata)
    require(
        module["Sum"] == pin["source_sum"]
        and module["Version"] == pin["version"]
        and module["Origin"]["Hash"] == pin["commit"],
        "shared_checksum_mismatch",
    )
    shutil.copyfile(
        Path(module["Dir"]) / "scripts/collect_mlflow_judge.py", out / "collect.py"
    )
    run(
        [
            GO,
            "install",
            "-trimpath",
            "-ldflags=-buildid=",
            pin["package"] + "@" + pin["version"],
        ],
        env=env,
        cwd=out,
        output=out / "build.log",
    )
    return out, env


def collect_quality(config, output, source, runtime):
    require(
        os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("GITHUB_REPOSITORY") == "fullsend-ai/auto-merge",
        "quality_main_only",
    )
    out = Path(output)
    out.mkdir(mode=0o700)
    q = config["judge_policy"]
    binding = {
        k: q[k]
        for k in [
            "schema_version",
            "experiment_id",
            "scorer",
            "source_id",
            "lookback_days",
        ]
    }
    binding["schema_version"] = "judge-binding/v1"
    binding["endpoint"] = os.environ["MLFLOW_READER_ENDPOINT"]
    private = Path(runtime) / "binding.json"
    private.write_text(json.dumps(binding))
    private.chmod(0o600)
    env = {
        "PATH": "/usr/bin:/bin",
        "MLFLOW_READER_USERNAME": os.environ["MLFLOW_READER_USERNAME"],
        "MLFLOW_READER_PASSWORD": os.environ["MLFLOW_READER_PASSWORD"],
    }
    result = subprocess.run(
        [
            "/usr/bin/python3",
            str(Path(runtime) / "collect.py"),
            "--binding",
            str(private),
            "--output",
            str(out / "quality.json"),
        ],
        env=env,
        capture_output=True,
        timeout=300,
    )
    private.unlink()
    require(result.returncode == 0, "quality_collection_failed")
    context = {
        "source_sha": source,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "config_sha256": digest(config),
    }
    (out / "quality-context.json").write_text(json.dumps(context))
    print(
        "Read-only quality collection completed; no trace payloads, endpoint or credentials retained."
    )


def assess(inputs, quality_dir, output):
    inputs = Path(inputs)
    config = bounded(inputs / "config.json")
    context = bounded(inputs / "context.json")
    output = Path(output)
    require(not output.exists(), "output_exists")
    output.mkdir(mode=0o700)
    quality = bounded(Path(quality_dir) / "quality.json")
    if context["phase"] == "enroll":
        provenance = bounded(Path(quality_dir) / "quality-context.json")
        require(
            provenance
            == {
                "source_sha": context["source_sha"],
                "run_id": context["run_id"],
                "attempt": context["attempt"],
                "config_sha256": digest(config),
            },
            "quality_context_mismatch",
        )
    require(context["config_sha256"] == digest(config), "configuration_changed")
    with tempfile.TemporaryDirectory(prefix="gemara-shared-gate-") as temporary:
        work = Path(temporary)
        prepared, env = prepare(config, work / "prepared")
        root = work / "root"
        root.mkdir(mode=0o755)
        shutil.copyfile(prepared / "bin/gemara-owner", root / "gemara-owner")
        (root / "gemara-owner").chmod(0o555)
        values = {
            "binding.json": config["binding"],
            "policy.json": config["judge_policy"],
            "quality.json": quality,
            "candidate.json": bounded(inputs / "candidate.json"),
        }
        for name, value in values.items():
            (root / name).write_text(json.dumps(value))
            (root / name).chmod(0o444)
        probe = work / "probe.go"
        probe.write_text(PROBE_SOURCE)
        run(
            [GO, "build", "-trimpath", "-o", str(root / "probe"), str(probe)],
            env=env,
            cwd=work,
            output=work / "probe-build.log",
        )
        (root / "probe").chmod(0o555)
        marker = work / "outside-marker"
        marker.write_text("SYNTHETIC_OUTSIDE_JAIL")
        jail = jail_prefix(root)
        runtime_env = {"PATH": "/usr/bin:/bin"}
        run(
            jail + ["/probe", str(marker)],
            env=runtime_env,
            cwd=work,
            output=work / "probe.log",
        )
        instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        code = run(
            jail
            + [
                "/gemara-owner",
                "assess-candidate",
                "--binding",
                "/binding.json",
                "--observation",
                "/candidate.json",
                "--judge-policy",
                "/policy.json",
                "--judge-observation",
                "/quality.json",
                "--at",
                instant,
            ],
            env=runtime_env,
            cwd=work,
            output=output / "assessment.json",
            accepted=(0, 2),
        )
        report = bounded(output / "assessment.json")
        require(
            (code == 0 and report["decision"] == "eligible")
            or (code == 2 and report["decision"] == "hold"),
            "assessment_exit_conflict",
        )
        require(
            report["authorization"] == "none" and report["mutation_permitted"] is False,
            "assessment_authority_invalid",
        )
        receipt = {
            "context": context,
            "quality": quality,
            "quality_sha256": digest(quality),
            "assessment_sha256": digest(report),
        }
        (output / "receipt.json").write_text(json.dumps(receipt))
        print(
            "Shared candidate checks: "
            + report["candidate"]["decision"]
            + "; quality: "
            + report["quality"]["state"]
            + " ("
            + report["quality"]["reason"]
            + "); combined: "
            + report["decision"]
            + ". No merge authority."
        )
    return report["decision"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "quality", "assess"])
    p.add_argument("--config")
    p.add_argument("--input")
    p.add_argument("--quality")
    p.add_argument("--output", required=True)
    p.add_argument("--source")
    p.add_argument("--runtime")
    a = p.parse_args()
    if a.command == "prepare":
        prepare(bounded(Path(a.config)), a.output)
    elif a.command == "quality":
        collect_quality(bounded(Path(a.config)), a.output, a.source, a.runtime)
    else:
        decision = assess(a.input, a.quality, a.output)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("eligible=" + str(decision == "eligible").lower() + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        reason = str(error)
        if not re.fullmatch(r"[a-z0-9_]{1,80}", reason):
            reason = "setup_or_evidence_invalid"
        raise SystemExit("Shared assessment held: " + reason)
