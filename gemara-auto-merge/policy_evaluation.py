"""Trusted host for native Gemara evaluation; every mode forbids mutation."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
from validate_gemara_artifacts import validate, ValidationError as ValidationError

ROOT = Path(__file__).resolve().parent


class InputError(ValueError):
    """Stable codes only: never echo a rejected value or environment content."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise InputError("invalid_timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("invalid_timestamp") from exc


def _unique(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise InputError("duplicate_json_key")
        value[key] = item
    return value


def load(path: Path) -> dict:
    if path.is_symlink():
        raise InputError("symlink_input")
    if not path.is_file():
        raise InputError("regular_file_input_required")
    limit = 1024 * 1024
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise InputError("input_too_large")
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                InputError("invalid_json_constant")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError("invalid_json") from exc
    if not isinstance(data, dict):
        raise InputError("invalid_document")
    return data


MODES = {"off", "shadow", "light", "gemara"}


def require(condition, code):
    if not condition:
        raise InputError(code)


def source_digests():
    paths = [
        ROOT / name
        for name in [
            "policy_evaluation.py",
            "github_pr_evidence.py",
            "authorize_auto_merge.py",
            "github_app_token_scope.py",
            "resolve_pr_from_event.py",
            "fullsend_review_evidence.py",
            "verify_recorded_trial_evidence.py",
            "validate_gemara_artifacts.py",
            "toolchain-lock.json",
        ]
    ]
    for directory in ("catalogs", "policies", "config"):
        paths += sorted((ROOT / directory).glob("*.json"))
    paths += [
        p
        for p in (ROOT / "native-evaluator").glob("*")
        if p.suffix == ".go" or p.name in {"go.mod", "go.sum"}
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }


def new_output(prefix):
    require(re.fullmatch(r"[a-z-]{1,20}", prefix), "invalid_output_prefix")
    parent = ROOT / "out"
    require(not parent.is_symlink(), "symlink_output")
    destination = parent / (
        prefix + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def load_bundle():
    catalogs, policies = {}, {}
    for name, kind in [
        ("catalogs/repository-readiness-and-pr-controls.json", "ControlCatalog"),
        ("policies/common-auto-merge-policy.json", "Policy"),
        ("policies/repository-auto-merge-policy.json", "Policy"),
    ]:
        data = load(ROOT / name)
        validate(data, kind)
        target = catalogs if kind == "ControlCatalog" else policies
        require(data["metadata"]["id"] not in target, "duplicate_artifact_id")
        target[data["metadata"]["id"]] = data
    return {
        "root_policy": "autonomy-repository",
        "catalogs": catalogs,
        "policies": policies,
    }


def subject(repository="example/fixture", configuration="c" * 64, candidate=False):
    value = {
        "repository": repository,
        "branch": "main",
        "configuration_sha256": configuration,
    }
    if candidate:
        value.update(head_sha="a" * 40, base_sha="b" * 40)
    return value


def validate_subject(value):
    require(
        isinstance(value, dict)
        and set(value)
        in [
            {"repository", "branch", "configuration_sha256"},
            {"repository", "branch", "configuration_sha256", "head_sha", "base_sha"},
        ],
        "invalid_subject",
    )
    require(
        type(value["repository"]) is str
        and re.fullmatch(
            r"(?:example|fullsend-ai)/[a-z0-9-]{1,50}", value["repository"]
        )
        and value["branch"] == "main",
        "unsupported_subject",
    )
    require(
        type(value["configuration_sha256"]) is str
        and re.fullmatch(r"[a-f0-9]{64}", value["configuration_sha256"]),
        "invalid_subject",
    )
    for key in ["head_sha", "base_sha"]:
        if key in value:
            require(
                type(value[key]) is str and re.fullmatch(r"[a-f0-9]{40}", value[key]),
                "invalid_subject",
            )


def assess(bundle, purpose, who, observations, as_of):
    validate_subject(who)
    require(
        purpose in {"readiness", "candidate"}
        and (("head_sha" in who) == (purpose == "candidate")),
        "wrong_subject_kind",
    )
    utc(as_of)
    # Callers cannot smuggle custom rules or executable methods into this boundary.
    require(set(bundle) == {"root_policy", "catalogs", "policies"}, "invalid_bundle")
    for kind, documents in [
        ("ControlCatalog", bundle["catalogs"]),
        ("Policy", bundle["policies"]),
    ]:
        require(
            isinstance(documents, dict) and 0 < len(documents) <= 8, "invalid_bundle"
        )
        for data in documents.values():
            validate(data, kind)
    require(
        isinstance(observations, dict) and len(observations) <= 40,
        "invalid_observations",
    )
    for key, o in observations.items():
        require(re.fullmatch(r"[A-Z][A-Z0-9-]{0,31}", key), "invalid_observation_id")
        require(
            isinstance(o, dict)
            and set(o) == {"subject_sha256", "collected_at", "trusted_source", "value"},
            "invalid_observation",
        )
        require(
            type(o["trusted_source"]) is bool
            and type(o["subject_sha256"]) is str
            and re.fullmatch(r"[a-f0-9]{64}", o["subject_sha256"]),
            "invalid_observation",
        )
        utc(o["collected_at"])
        v = o["value"]
        require(
            v is None
            or type(v) is bool
            or (type(v) is int and 0 <= v <= 100)
            or (type(v) is str and re.fullmatch(r"[A-Za-z0-9 -]{1,60}", v)),
            "unbounded_observation",
        )
    value = dict(
        bundle,
        schema_version="gemara-evaluation/v1",
        purpose=purpose,
        repository=who["repository"],
        subject_sha256=digest(who),
        as_of=as_of,
        observations=observations,
    )
    raw = json.dumps(value, allow_nan=False)
    require(len(raw.encode()) <= 1024 * 1024, "request_too_large")
    lock = load(ROOT / "evaluator-build-lock.json")
    binary = ROOT / ".tools/gemara-evaluator"
    require(
        binary.is_file()
        and not binary.is_symlink()
        and hashlib.sha256(binary.read_bytes()).hexdigest()
        == lock["evaluator_binary_sha256"],
        "build_required",
    )
    require(
        all(
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
            for name, expected in lock["evaluator_sources"].items()
        ),
        "source_changed",
    )
    try:
        child = subprocess.run(
            [str(binary)],
            input=raw,
            text=True,
            capture_output=True,
            timeout=15,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError("gemara_unavailable") from exc
    require(len(child.stdout) <= 1024 * 1024, "oversized_result")
    if child.returncode:
        try:
            code = json.loads(child.stdout)["error"]
        except (KeyError, ValueError):
            code = "invalid_policy_or_evidence"
        require(
            type(code) is str and re.fullmatch(r"[a-z_]{1,80}", code),
            "invalid_gemara_error",
        )
        raise InputError("gemara_" + code)
    result = json.loads(child.stdout)
    require(
        result["engine"] == "gemara"
        and result["mutation_permitted"] is False
        and result["assessments"],
        "invalid_result",
    )
    require(
        result["decision"]
        == (
            "eligible"
            if all(row["state"] == "passed" for row in result["assessments"])
            else "hold"
        ),
        "inconsistent_result",
    )
    validate(result["evaluation_log"], "EvaluationLog")
    result["request_sha256"] = digest(value)
    return result


def qualification(bundle, who, as_of, observations):
    result = assess(bundle, "readiness", who, observations, as_of)
    return {
        "subject": who,
        "policy_sha256": digest(bundle),
        "issued_at": as_of,
        "decision": result["decision"],
        "result": result,
        "mutation_permitted": False,
    }


def gate(bundle, who, as_of, observations, mode, receipt):
    require(mode in MODES, "unsupported_mode")
    validate_subject(who)
    reasons, result = [], None
    if mode == "off":
        reasons.append("mode_off")
    else:
        ready = {k: v for k, v in who.items() if k not in {"head_sha", "base_sha"}}
        if (
            receipt is None
            or receipt["subject"] != ready
            or receipt["policy_sha256"] != digest(bundle)
            or receipt["decision"] != "eligible"
        ):
            reasons.append("qualification_unavailable")
        elif not 0 <= (utc(as_of) - utc(receipt["issued_at"])).total_seconds() <= 600:
            reasons.append("qualification_expired")
        result = assess(bundle, "candidate", who, observations, as_of)
        if result["decision"] != "eligible":
            reasons.append("candidate_held")
        if (
            mode == "light"
            and observations.get("AM-CLASS", {}).get("value") != "dependency-digest"
        ):
            reasons.append("outside_light_class")
    return {
        "mode": mode,
        "engine": "gemara",
        "decision": "would_allow" if not reasons else "hold",
        "reasons": reasons,
        "evaluation": result,
        "policy_sha256": digest(bundle),
        "subject_sha256": digest(who),
        "mutation_permitted": False,
        "authorized_actions": [],
        "qualification_receipt_is_local_unsigned": True,
    }
