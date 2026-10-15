"""Experimental policy-adapter boundary. All outputs forbid mutation."""

from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import re
import subprocess

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


MODES = {"off", "shadow", "light", "policy"}
KINDS = {"boolean", "maximum", "equals", "member"}


def source_digests():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in [
            "platform_lab.py",
            "github_observe.py",
            "sdk/main.go",
            "sdk/go.mod",
            "sdk/go.sum",
        ]
    }


def new_output(prefix):
    require(
        type(prefix) is str and re.fullmatch(r"[a-z-]{1,20}", prefix),
        "invalid_output_prefix",
    )
    parent = ROOT / "out"
    require(not parent.is_symlink(), "symlink_output")
    destination = parent / (
        prefix + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def require(condition, code):
    if not condition:
        raise InputError(code)


def fields(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), "invalid_fields")


def resolve(shared, repository, trusted=True):
    """A closed lab profile composer, not a general Gemara policy resolver."""
    require(trusted is True, "untrusted_policy")
    fields(
        shared,
        {
            "version",
            "maximum_age_seconds",
            "maximum_risk",
            "classes",
            "light_classes",
            "readiness",
            "candidate",
        },
    )
    fields(repository, {"version", "maximum_risk", "classes", "additional_checks"})
    require(shared["version"] == repository["version"] == 1, "unsupported_policy")
    require(
        type(shared["maximum_age_seconds"]) is int
        and 0 < shared["maximum_age_seconds"] <= 600,
        "invalid_freshness",
    )
    require(
        type(repository["maximum_risk"]) is int
        and type(shared["maximum_risk"]) is int
        and 0 <= repository["maximum_risk"] <= shared["maximum_risk"] <= 5,
        "minimum_weakened",
    )
    for values in [shared["classes"], shared["light_classes"], repository["classes"]]:
        require(
            isinstance(values, list)
            and values
            and all(type(x) is str and re.fullmatch(r"[a-z-]{1,30}", x) for x in values)
            and len(set(values)) == len(values),
            "invalid_classes",
        )
    require(
        set(repository["classes"]) <= set(shared["classes"])
        and set(shared["light_classes"]) <= set(shared["classes"]),
        "scope_weakened",
    )
    result = copy.deepcopy(shared)
    result["maximum_risk"] = repository["maximum_risk"]
    result["classes"] = repository["classes"]
    require(
        isinstance(repository["additional_checks"], list), "invalid_additional_checks"
    )
    result["candidate"] += copy.deepcopy(repository["additional_checks"])
    for purpose in ["readiness", "candidate"]:
        rules = result[purpose]
        require(isinstance(rules, list) and 1 <= len(rules) <= 40, "invalid_rules")
        ids = []
        for rule in rules:
            fields(rule, {"id", "kind", "expected"})
            require(
                type(rule["id"]) is str
                and re.fullmatch(r"[A-Z][A-Z0-9-]{0,31}", rule["id"]),
                "invalid_rule_id",
            )
            require(rule["kind"] in KINDS, "unsupported_rule")
            if rule["kind"] == "maximum":
                require(
                    type(rule["expected"]) is int and 0 <= rule["expected"] <= 5,
                    "invalid_threshold",
                )
            if rule["kind"] == "boolean":
                require(rule["expected"] is True, "minimum_weakened")
            if rule["kind"] == "member":
                require(
                    isinstance(rule["expected"], list)
                    and rule["expected"]
                    and all(
                        type(v) is str and re.fullmatch(r"[a-z-]{1,30}", v)
                        for v in rule["expected"]
                    ),
                    "invalid_members",
                )
            if rule["kind"] == "equals":
                require(
                    type(rule["expected"]) is str
                    and re.fullmatch(r"[A-Za-z0-9 -]{1,60}", rule["expected"]),
                    "invalid_expected",
                )
            ids.append(rule["id"])
        require(len(ids) == len(set(ids)), "duplicate_control")
    required_readiness = {
        "AR-RULES",
        "AR-CHECKS",
        "AR-REVIEWS",
        "AR-STATUS",
        "AR-TESTS",
        "AR-ISOLATION",
        "AR-QUEUE",
        "AR-HISTORY",
    }
    required_candidate = {
        "AM-CI",
        "AM-REVIEW",
        "AM-FINDINGS",
        "AM-RISK",
        "AM-CLASS",
        "AM-PROTECTED",
    }
    require(
        required_readiness <= {r["id"] for r in result["readiness"]}
        and required_candidate <= {r["id"] for r in result["candidate"]},
        "minimum_removed",
    )
    for rule in result["candidate"]:
        if rule["id"] == "AM-RISK":
            require(rule["kind"] == "maximum", "minimum_weakened")
            rule["expected"] = result["maximum_risk"]
        elif rule["id"] == "AM-CLASS":
            require(rule["kind"] == "member", "minimum_weakened")
            rule["expected"] = result["classes"]
        elif rule["id"] in required_candidate:
            require(rule["kind"] == "boolean", "minimum_weakened")
    require(
        all(
            r["kind"] == "boolean"
            for r in result["readiness"]
            if r["id"] in required_readiness
        ),
        "minimum_weakened",
    )
    result["sources"] = {
        "shared_sha256": digest(shared),
        "repository_sha256": digest(repository),
    }
    result["effective_sha256"] = digest(result)
    return result


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


def request(effective, purpose, who, observations, as_of):
    require(purpose in {"readiness", "candidate"}, "invalid_purpose")
    validate_subject(who)
    require(("head_sha" in who) == (purpose == "candidate"), "wrong_subject_kind")
    utc(as_of)
    value = {
        "schema_version": "adapter-request/v1",
        "subject_sha256": digest(who),
        "as_of": as_of,
        "maximum_age_seconds": effective["maximum_age_seconds"],
        "rules": copy.deepcopy(effective[purpose]),
        "observations": observations,
    }
    validate_request(value)
    return value


def validate_request(value):
    fields(
        value,
        {
            "schema_version",
            "subject_sha256",
            "as_of",
            "maximum_age_seconds",
            "rules",
            "observations",
        },
    )
    require(
        value["schema_version"] == "adapter-request/v1"
        and re.fullmatch(r"[a-f0-9]{64}", value["subject_sha256"]),
        "invalid_request",
    )
    utc(value["as_of"])
    require(
        type(value["maximum_age_seconds"]) is int
        and 0 < value["maximum_age_seconds"] <= 600,
        "invalid_request",
    )
    require(
        isinstance(value["rules"], list) and 0 < len(value["rules"]) <= 40,
        "invalid_request",
    )
    ids = []
    for rule in value["rules"]:
        fields(rule, {"id", "kind", "expected"})
        require(
            type(rule["id"]) is str
            and re.fullmatch(r"[A-Z][A-Z0-9-]{0,31}", rule["id"])
            and rule["kind"] in KINDS,
            "invalid_rule",
        )
        ids.append(rule["id"])
        expected = rule["expected"]
        if rule["kind"] == "boolean":
            require(expected is True, "invalid_expected")
        elif rule["kind"] == "maximum":
            require(type(expected) is int and 0 <= expected <= 5, "invalid_expected")
        elif rule["kind"] == "equals":
            require(
                type(expected) is str
                and re.fullmatch(r"[A-Za-z0-9 -]{1,60}", expected),
                "invalid_expected",
            )
        else:
            require(
                isinstance(expected, list)
                and expected
                and all(
                    type(v) is str and re.fullmatch(r"[a-z-]{1,30}", v)
                    for v in expected
                ),
                "invalid_expected",
            )
    require(len(ids) == len(set(ids)), "duplicate_control")
    require(
        isinstance(value["observations"], dict)
        and set(value["observations"]) <= set(ids),
        "unexpected_observations",
    )
    for key, observation in value["observations"].items():
        fields(
            observation, {"subject_sha256", "collected_at", "trusted_source", "value"}
        )
        require(
            type(observation["trusted_source"]) is bool
            and type(observation["subject_sha256"]) is str
            and re.fullmatch(r"[a-f0-9]{64}", observation["subject_sha256"]),
            "invalid_observation",
        )
        utc(observation["collected_at"])
        v = observation["value"]
        require(
            v is None
            or type(v) in {bool, int}
            or (type(v) is str and re.fullmatch(r"[A-Za-z0-9 -]{1,60}", v)),
            "unbounded_observation",
        )
        if type(v) is int:
            require(0 <= v <= 100, "invalid_observation")


def observations_for(req_subject, rules, as_of):
    """Fabricated positive inputs, used only by synthetic demos/tests."""
    return {
        r["id"]: {
            "subject_sha256": digest(req_subject),
            "collected_at": as_of,
            "trusted_source": True,
            "value": (
                r["expected"][0]
                if r["kind"] == "member"
                else 1
                if r["kind"] == "maximum"
                else r["expected"]
            ),
        }
        for r in rules
    }


def reference_adapter(value):
    """Independent native JSON adapter; does not import or invoke Gemara."""
    validate_request(value)
    rows = []
    for rule in value["rules"]:
        obs = value["observations"].get(rule["id"])
        state, reason = "unknown", "missing"
        if obs is not None:
            age = (utc(value["as_of"]) - utc(obs["collected_at"])).total_seconds()
            if (
                not obs["trusted_source"]
                or obs["subject_sha256"] != value["subject_sha256"]
            ):
                reason = "untrusted_or_wrong_subject"
            elif age < 0 or age > value["maximum_age_seconds"]:
                reason = "stale_or_future"
            else:
                v, kind = obs["value"], rule["kind"]
                valid = (
                    type(v) is bool
                    if kind == "boolean"
                    else type(v) is int and v >= 0
                    if kind == "maximum"
                    else type(v) is str
                )
                if valid:
                    passed = (
                        v is True
                        if kind == "boolean"
                        else v <= rule["expected"]
                        if kind == "maximum"
                        else v in rule["expected"]
                        if kind == "member"
                        else v == rule["expected"]
                    )
                    state, reason = (
                        ("passed", "satisfied")
                        if passed
                        else ("failed", "condition_failed")
                    )
                else:
                    reason = "invalid_value"
        rows.append({"id": rule["id"], "state": state, "reason": reason})
    return {
        "adapter": "native-json-reference",
        "decision": "eligible" if all(x["state"] == "passed" for x in rows) else "hold",
        "assessments": sorted(rows, key=lambda r: r["id"]),
        "mutation_permitted": False,
    }


def gemara_adapter(value):
    validate_request(value)
    binary = ROOT / ".tools" / "gemara-adapter"
    lock = load(ROOT / "build-lock.json")
    require(
        binary.is_file()
        and not binary.is_symlink()
        and hashlib.sha256(binary.read_bytes()).hexdigest()
        == lock["adapter_binary_sha256"],
        "adapter_build_required",
    )
    sources = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in lock["adapter_sources"]
    }
    require(sources == lock["adapter_sources"], "adapter_source_changed")
    try:
        r = subprocess.run(
            [str(binary)],
            input=json.dumps(value),
            capture_output=True,
            text=True,
            timeout=15,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError("adapter_unavailable") from exc
    require(r.returncode == 0 and len(r.stdout) <= 1024 * 1024, "adapter_failed")
    result = json.loads(r.stdout)
    require(
        result["mutation_permitted"] is False and result["adapter"] == "gemara-sdk",
        "invalid_adapter_result",
    )
    return result


def assess(value, adapter):
    result = {"gemara-sdk": gemara_adapter, "native-json-reference": reference_adapter}[
        adapter
    ](value)
    expected = sorted(r["id"] for r in value["rules"])
    require(
        sorted(r["id"] for r in result["assessments"]) == expected, "incomplete_result"
    )
    require(
        all(
            r["state"] in {"passed", "failed", "unknown"} for r in result["assessments"]
        ),
        "unsupported_result",
    )
    require(
        result["decision"]
        == (
            "eligible"
            if all(r["state"] == "passed" for r in result["assessments"])
            else "hold"
        ),
        "inconsistent_result",
    )
    result["request_sha256"] = digest(value)
    return result


def qualification(effective, who, as_of, observations, adapter):
    req = request(effective, "readiness", who, observations, as_of)
    outcome = assess(req, adapter)
    return {
        "subject": who,
        "policy_sha256": effective["effective_sha256"],
        "issued_at": as_of,
        "request_sha256": digest(req),
        "decision": outcome["decision"],
        "adapter": adapter,
        "result": outcome,
        "mutation_permitted": False,
    }


def gate(effective, who, as_of, observations, mode, receipt, adapter):
    require(mode in MODES, "unsupported_mode")
    require(adapter in {"gemara-sdk", "native-json-reference"}, "unsupported_adapter")
    validate_subject(who)
    reasons = []
    result = None
    if mode == "off":
        reasons.append("mode_off")
    else:
        ready_subject = {
            k: v for k, v in who.items() if k not in {"head_sha", "base_sha"}
        }
        if (
            receipt is None
            or receipt["subject"] != ready_subject
            or receipt["policy_sha256"] != effective["effective_sha256"]
            or receipt["adapter"] != adapter
            or receipt["decision"] != "eligible"
        ):
            reasons.append("qualification_unavailable")
        elif (
            not 0
            <= (utc(as_of) - utc(receipt["issued_at"])).total_seconds()
            <= effective["maximum_age_seconds"]
        ):
            reasons.append("qualification_expired")
        req = request(effective, "candidate", who, observations, as_of)
        result = assess(req, adapter)
        if result["decision"] != "eligible":
            reasons.append("candidate_held")
        if (
            mode == "light"
            and observations.get("AM-CLASS", {}).get("value")
            not in effective["light_classes"]
        ):
            reasons.append("outside_light_class")
    return {
        "mode": mode,
        "adapter": adapter,
        "decision": "would_allow" if not reasons else "hold",
        "reasons": reasons,
        "evaluation": result,
        "policy_sha256": effective["effective_sha256"],
        "subject_sha256": digest(who),
        "mutation_permitted": False,
        "authorized_actions": [],
        "qualification_receipt_is_local_unsigned": True,
    }
