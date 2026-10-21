#!/usr/bin/env python3
"""Build a checksum-pinned data-only checker; run without write credentials.

GitHub calls this in a separate permissions:{} job with no inherited secrets.
GitLab additionally requires an unprotected MR ref and a different-UID chroot.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def require(value, reason):
    if not value:
        raise ValueError(reason)


def bounded(path, maximum=128 * 1024):
    require(
        not path.is_symlink() and path.is_file() and path.stat().st_size <= maximum,
        "invalid_input_file",
    )
    return json.loads(path.read_text())


def run(args, *, env, cwd, output, accepted=(0,)):
    with output.open("wb") as stdout, tempfile.TemporaryFile() as stderr:
        child = subprocess.run(
            args, env=env, cwd=cwd, stdout=stdout, stderr=stderr, timeout=180
        )
    require(
        child.returncode in accepted, "command_failed_exit_" + str(child.returncode)
    )
    require(output.stat().st_size <= 128 * 1024, "command_output_too_large")
    return child.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--pin", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chroot", action="store_true")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        ref = os.environ.get("GITHUB_REF", "")
        default = os.environ.get("GEMARA_DEFAULT_REF", "")
        require(
            default.startswith("refs/heads/")
            and ref.startswith("refs/heads/")
            and ref not in {default, "refs/heads/main"},
            "default_branch_replay_forbidden",
        )
    source = Path(args.input).resolve()
    context = bounded(source / "context.json")
    require(
        context["mode"] == "retained-review-replay"
        and context["authorization"] == "none",
        "replay_context_required",
    )
    require(
        re.fullmatch(r"[a-f0-9]{40}", context["head_sha"])
        and type(context["maximum_risk"]) is int
        and 1 <= context["maximum_risk"] <= 5,
        "invalid_review_context",
    )
    pin = bounded(Path(args.pin))
    require(
        pin["schema_version"] == "shared-review-tool/v1"
        and pin["module"] == "github.com/ascerra/fullsend-gemara-integration"
        and pin["package"] == pin["module"] + "/cmd/gemara-owner",
        "unapproved_module",
    )
    require(
        re.fullmatch(r"[a-f0-9]{40}", pin["commit"])
        and re.fullmatch(r"v0\.0\.0-[0-9]{14}-" + pin["commit"][:12], pin["version"])
        and pin["go_version"] == "1.26.9",
        "invalid_source_pin",
    )
    go = shutil.which("go")
    require(go is not None, "bootstrap_go_unavailable")
    if args.chroot:
        require(
            os.geteuid() == 0 and os.environ.get("CI_COMMIT_REF_PROTECTED") == "false",
            "gitlab_chroot_requires_root_unprotected_job",
        )
        chroot = shutil.which("chroot")
        require(chroot is not None, "chroot_unavailable")
    output = Path(args.output)
    require(not output.exists(), "output_already_exists")
    output.mkdir(mode=0o700, parents=True)
    with tempfile.TemporaryDirectory(prefix="gemara-isolated-check-") as temporary:
        work = Path(temporary)
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(work),
            "GOPATH": str(work / "gopath"),
            "GOCACHE": str(work / "cache"),
            "GOBIN": str(work / "bin"),
            "GOTOOLCHAIN": "go1.26.9",
            "GOTELEMETRY": "off",
            "CGO_ENABLED": "0",
            "GOPROXY": "https://proxy.golang.org",
            "GOSUMDB": "sum.golang.org",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
        }
        # Go's trusted compiler does not run module code; cgo/generate are disabled.
        metadata = work / "module.json"
        run(
            [go, "mod", "download", "-json", pin["module"] + "@" + pin["version"]],
            env=env,
            cwd=work,
            output=metadata,
        )
        module = bounded(metadata)
        require(
            module["Sum"] == pin["source_sum"]
            and module["Version"] == pin["version"]
            and module["Origin"]["Hash"] == pin["commit"],
            "shared_source_checksum_mismatch",
        )
        run(
            [
                go,
                "install",
                "-trimpath",
                "-ldflags=-buildid=",
                pin["package"] + "@" + pin["version"],
            ],
            env=env,
            cwd=work,
            output=work / "build.log",
        )
        binary = work / "bin/gemara-owner"
        require(binary.is_file(), "shared_binary_missing")
        root = work / "root"
        root.mkdir(mode=0o755)
        shutil.copyfile(binary, root / "gemara-owner")
        (root / "gemara-owner").chmod(0o555)
        for name in ["result.json", "ledger.json"]:
            bounded(source / name)
            shutil.copyfile(source / name, root / name)
            (root / name).chmod(0o444)
        prefix = [str(root / "gemara-owner")]
        file_prefix = str(root)
        runtime_env = {"PATH": "/usr/bin:/bin"}
        if args.chroot:
            # No host mounts or /proc. Drop UID/GID before running shared code.
            jail = [chroot, "--userspec=65534:65534", "--groups=65534", str(root)]
            probe = work / "probe.go"
            probe.write_text(
                'package main\nimport("os")\nfunc main(){if os.Getuid()!=65534{os.Exit(10)};for _,k:=range []string{"CI_JOB_TOKEN","REVIEW_TOKEN","GH_TOKEN","GITHUB_TOKEN"}{if os.Getenv(k)!=""{os.Exit(11)}};if _,e:=os.Stat("/proc");!os.IsNotExist(e){os.Exit(12)}}\n'
            )
            run(
                [go, "build", "-trimpath", "-o", str(root / "probe"), str(probe)],
                env=env,
                cwd=work,
                output=work / "probe-build.log",
            )
            (root / "probe").chmod(0o555)
            run(jail + ["/probe"], env=runtime_env, cwd=work, output=work / "probe.log")
            print(
                "Different-UID chroot probe passed; no host /proc or inherited tokens."
            )
            prefix = jail + ["/gemara-owner"]
            file_prefix = ""
        projection = output / "projection.json"
        run(
            prefix
            + [
                "project-review",
                "--result",
                file_prefix + "/result.json",
                "--ledger",
                file_prefix + "/ledger.json",
                "--head",
                context["head_sha"],
            ],
            env=runtime_env,
            cwd=work,
            output=projection,
        )
        value = bounded(projection)
        require(
            value["schema_version"] == "review-projection/v1"
            and value["head_sha"] == context["head_sha"]
            and value["authorization"] == "none"
            and value["mutation_permitted"] is False,
            "invalid_shared_projection",
        )
        shutil.copyfile(projection, root / "projection.json")
        (root / "projection.json").chmod(0o444)
        code = run(
            prefix
            + [
                "check-review",
                "--projection",
                file_prefix + "/projection.json",
                "--head",
                context["head_sha"],
                "--maximum-risk",
                str(context["maximum_risk"]),
            ],
            env=runtime_env,
            cwd=work,
            output=output / "assessment.json",
            accepted=(0, 2),
        )
        report = bounded(output / "assessment.json")
        require(
            report["schema_version"] == "review-check/v1"
            and report["head_sha"] == context["head_sha"]
            and report["authorization"] == "none"
            and report["mutation_permitted"] is False,
            "invalid_shared_assessment",
        )
        require(
            (code == 0 and report["decision"] == "eligible")
            or (code == 2 and report["decision"] == "hold"),
            "assessment_exit_conflict",
        )
        require(
            isinstance(report.get("reason"), str)
            and re.fullmatch(r"[a-z0-9_-]{1,80}", report["reason"]),
            "invalid_assessment_reason",
        )
        print(
            "Shared native Gemara Review check: "
            + report["decision"]
            + " ("
            + report["reason"]
            + "). Retained replay only; no merge authority."
        )
        return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        reason = str(error)
        if not re.fullmatch(r"[a-z0-9_-]{1,80}", reason):
            reason = "replay_setup_failed"
        raise SystemExit("Shared Review assessment failed closed: " + reason)
