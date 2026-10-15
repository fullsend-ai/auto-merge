"""Consume the official v2 Review projection; retain no review prose or anchors."""

import base64
import binascii
from datetime import datetime
import json
import re

BOT_ID = 278716355
BOT_LOGIN = "fullsend-ai-review[bot]"
SUMMARY = "<!-- fullsend:review-agent -->"
HEAD = re.compile(r"^<!-- \*\*Head SHA:\*\* ([0-9a-f]{40}) -->$", re.M)
PROJECTION = re.compile(
    r"^<!-- fullsend:review-findings-v2:([A-Za-z0-9+/=]+) -->$", re.M
)
ID = re.compile(r"f_[A-Za-z0-9]{1,128}\Z")
SEVERITIES = {"info", "low", "medium", "high", "critical"}
STATUSES = {"open", "reclassified", "resolved_by_change", "dismissed_by_human"}
CATEGORIES = set(
    """
logic-error nil-deref off-by-one edge-case api-contract missing-test test-inadequate
pattern-violation test-weakened test-removed mock-loosened assertion-weakened
coverage-reduced test-poisoning split-payload stale-reference auth-bypass
rbac-violation data-exposure privilege-escalation injection-vuln sandbox-escape
xss ssrf insecure-deserialization prompt-injection unicode-steganography
bidi-override homoglyph-attack instruction-smuggling fail-open permission-expansion
permission-reduction role-escalation workflow-permission secret-exposure
scope-exceeded tier-mismatch unauthorized-change scope-creep missing-authorization
misleading-label design-direction complexity-ratio misplaced-abstraction
architectural-conflict design-smell over-engineering under-engineering scope-bundling
naming-convention error-handling-idiom api-shape code-organization doc-style
pattern-inconsistency stale-doc missing-doc incorrect-doc incomplete-doc breaking-api
breaking-schema breaking-config breaking-cli missing-deprecation missing-version-bump
backward-incompatible
""".split()
)


def producer(row):
    user = row.get("user") or {}
    return (
        user.get("id") == BOT_ID
        and user.get("login") == BOT_LOGIN
        and user.get("type") == "Bot"
    )


def current_section(body):
    if not isinstance(body, str) or len(body) > 65536:
        return ""
    # Sticky comments carry old results; never use their markers as current evidence.
    return re.split(
        r"<!-- sticky:history-start -->|<summary>Previous run(?: \([0-9]+\))?</summary>",
        body,
        maxsplit=1,
    )[0].replace("\r\n", "\n")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


def ledger_clear(encoded):
    """A conservative boolean: every open finding, including info, holds."""
    if len(encoded) > 60000:
        raise ValueError("oversized")
    data = json.loads(
        base64.b64decode(encoded, validate=True), object_pairs_hook=unique_object
    )
    if not isinstance(data, dict) or set(data) - {
        "version",
        "action",
        "findings",
        "dispositions",
    }:
        raise ValueError("shape")
    if type(data.get("version")) is not int or data["version"] != 2:
        raise ValueError("version")
    if data.get("action") not in {"approve", "request-changes", "comment", "reject"}:
        raise ValueError("action")
    findings, dispositions = data.get("findings"), data.get("dispositions", [])
    if not isinstance(findings, list) or not isinstance(dispositions, list):
        raise ValueError("rows")
    if len(findings) > 500 or len(dispositions) > 500:
        raise ValueError("oversized")
    rows, states = {}, {}
    for row in findings:
        if not isinstance(row, dict) or set(row) - {
            "id",
            "severity",
            "category",
            "file",
            "line",
            "actionable",
        }:
            raise ValueError("finding")
        key = row.get("id")
        if not isinstance(key, str) or not ID.fullmatch(key) or key in rows:
            raise ValueError("id")
        if row.get("severity") not in SEVERITIES or not isinstance(
            row.get("category"), str
        ):
            raise ValueError("finding")
        if row["category"] not in CATEGORIES or "file" not in row:
            raise ValueError("finding")
        if row["file"] is not None and not isinstance(row["file"], str):
            raise ValueError("anchor")
        if "line" in row and (type(row["line"]) is not int or row["line"] < 1):
            raise ValueError("anchor")
        if "actionable" in row and type(row["actionable"]) is not bool:
            raise ValueError("actionable")
        rows[key] = row
    for row in dispositions:
        if not isinstance(row, dict) or set(row) != {"id", "status"}:
            raise ValueError("disposition")
        key, state = row["id"], row["status"]
        if (
            not isinstance(key, str)
            or key not in rows
            or key in states
            or state not in STATUSES
        ):
            raise ValueError("disposition")
        if state == "dismissed_by_human" and rows[key]["severity"] in {
            "high",
            "critical",
        }:
            raise ValueError("unsupported_dismissal")
        states[key] = state
    return data["action"] == "approve" and all(
        states.get(key) in {"resolved_by_change", "dismissed_by_human"} for key in rows
    )


def findings(head, reviews, comments):
    unknown = {"value": None, "reason": "fullsend_findings_unavailable"}
    if reviews is None or comments is None:
        return unknown
    reviews = [r for r in reviews if producer(r)]
    summaries = [
        c for c in comments if producer(c) and SUMMARY in current_section(c.get("body"))
    ]
    if not reviews or not summaries:
        return unknown
    review = max(reviews, key=lambda r: r.get("id", 0))
    comment = max(summaries, key=lambda c: (c.get("updated_at", ""), c.get("id", 0)))
    body = current_section(comment.get("body"))
    heads, projections = HEAD.findall(body), PROJECTION.findall(body)
    if review.get("commit_id") != head or heads != [head]:
        return {"value": None, "reason": "fullsend_findings_wrong_revision"}
    if review.get("state") != "APPROVED":
        return {"value": False, "reason": "fullsend_review_not_approved"}
    try:
        # The summary is posted immediately before its review. Reject a later edit
        # or an older result left over from a different review of the same revision.
        elapsed = (
            datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))
            - datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
        ).total_seconds()
        if (
            not 0 <= elapsed <= 300
            or len(projections) != 1
            or body.count("<!-- fullsend:review-findings-") != 1
        ):
            raise ValueError("binding")
        clear = ledger_clear(projections[0])
    except (ValueError, TypeError, KeyError, RecursionError, binascii.Error):
        return {"value": None, "reason": "fullsend_findings_invalid_or_unbound"}
    return {
        "value": clear,
        "reason": "fullsend_v2_ledger_clear" if clear else "fullsend_v2_ledger_holds",
        "review_id": review["id"],
        "summary_comment_id": comment["id"],
    }


def risk_gap(comments):
    # The official risk marker currently contains no revision. Do not turn its
    # score into candidate evidence through time correlation, labels or prose.
    if comments is None:
        return "fullsend_risk_unavailable"
    if any(
        producer(c)
        and "<!-- fullsend:risk-assessment -->" in current_section(c.get("body"))
        for c in comments
    ):
        return "fullsend_risk_missing_revision_binding"
    return "fullsend_risk_missing"


RISK_RECEIPT = re.compile(r"^<!-- fullsend:review-risk-v1:([A-Za-z0-9+/=]+) -->$", re.M)


def risk(head, reviews, comments, verify_producer):
    """Accept only a bound host receipt from a verified completed Fullsend run."""
    absent = {"value": None, "reason": risk_gap(comments)}
    ledger = findings(head, reviews, comments)
    if "summary_comment_id" not in ledger:
        return absent
    comment = next(c for c in comments if c.get("id") == ledger["summary_comment_id"])
    body = current_section(comment.get("body"))
    receipts = RISK_RECEIPT.findall(body)
    if not receipts:
        return absent
    try:
        if (
            len(receipts) != 1
            or body.count("<!-- fullsend:review-risk-") != 1
            or len(receipts[0]) > 2048
        ):
            raise ValueError("receipt")
        data = json.loads(
            base64.b64decode(receipts[0], validate=True),
            object_pairs_hook=unique_object,
        )
        if not isinstance(data, dict) or set(data) != {
            "version",
            "head_sha",
            "score",
            "level",
            "config_sha",
            "run_id",
            "run_attempt",
        }:
            raise ValueError("receipt")
        if (
            type(data["version"]) is not int
            or data["version"] != 1
            or data["head_sha"] != head
        ):
            raise ValueError("binding")
        score = data["score"]
        if (
            type(score) is not int
            or not 1 <= score <= 5
            or data["level"]
            != ["low", "moderate", "elevated", "high", "critical"][score - 1]
        ):
            raise ValueError("risk")
        if not isinstance(data["config_sha"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", data["config_sha"]
        ):
            raise ValueError("binding")
        for key, maximum in [("run_id", 10**15 - 1), ("run_attempt", 999999)]:
            if type(data[key]) is not int or not 1 <= data[key] <= maximum:
                raise ValueError("run")
    except (ValueError, TypeError, RecursionError, binascii.Error):
        return {"value": None, "reason": "fullsend_risk_receipt_invalid"}
    if not verify_producer(data):
        return {"value": None, "reason": "fullsend_risk_producer_unverified"}
    return {
        "value": score,
        "reason": "fullsend_lab_risk_receipt_verified",
        "review_id": ledger["review_id"],
        "summary_comment_id": ledger["summary_comment_id"],
        "run_id": data["run_id"],
        "run_attempt": data["run_attempt"],
        "config_sha": data["config_sha"],
    }
