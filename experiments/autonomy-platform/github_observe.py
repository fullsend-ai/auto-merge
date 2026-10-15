#!/usr/bin/env python3
"""Read public PR metadata; never fetch logs, download artifacts or perform writes."""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import re
import urllib.error
import urllib.request

from platform_lab import (
    ROOT,
    InputError,
    digest,
    gate,
    new_output,
    qualification,
    require,
    load_bundle,
    ValidationError,
    source_digests,
)

REPOSITORY = "fullsend-ai/auto-merge"
CHECK_NAMES = {"Example contract", "Delayed integration (4 minutes)"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InputError("github_redirect_refused")


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        self.errors = set()

    def get(self, path):
        require(
            path.startswith("repos/" + REPOSITORY + "/")
            and not any(x in path for x in ["..", "\n", "\r", "#", ":"]),
            "unsupported_endpoint",
        )
        headers = {
            "User-Agent": "autonomy-shadow-observer",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            with self.opener.open(
                urllib.request.Request(
                    "https://api.github.com/" + path, headers=headers, method="GET"
                ),
                timeout=20,
            ) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "github_response_too_large")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            self.errors.add("github_http_" + str(exc.code))
        except (OSError, json.JSONDecodeError):
            self.errors.add("github_unavailable")
        return None

    def pages(self, endpoint, key=None):
        rows = []
        for page in range(1, 11):
            data = self.get(
                endpoint
                + ("&" if "?" in endpoint else "?")
                + f"per_page=100&page={page}"
            )
            if data is None:
                return None
            batch = data.get(key) if key and isinstance(data, dict) else data
            require(isinstance(batch, list), "unexpected_github_response")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        self.errors.add("github_pagination_incomplete")
        return None


def normalize(pr, checks, reviews, files):
    """Reduce API responses to closed-domain values, without retaining their text."""
    head = pr["head"]["sha"]
    ci = None
    if checks is not None:
        selected = {
            name: [
                c
                for c in checks
                if c.get("name") == name
                and c.get("head_sha") == head
                and (c.get("app") or {}).get("id") == 15368
            ]
            for name in CHECK_NAMES
        }
        if all(len(v) == 1 for v in selected.values()):
            latest = [v[0] for v in selected.values()]
            if any(
                c.get("status") == "completed" and c.get("conclusion") != "success"
                for c in latest
            ):
                ci = False
            elif all(c.get("status") == "completed" for c in latest):
                ci = True
    approved = None
    seen = False
    if reviews is not None:
        matching = [
            r
            for r in reviews
            if (r.get("user") or {}).get("login") == "fullsend-ai-review[bot]"
            and (r.get("user") or {}).get("type") == "Bot"
        ]
        seen = bool(matching)
        decisive = [
            r
            for r in matching
            if r.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
        ]
        if decisive:
            latest = max(decisive, key=lambda r: r.get("id", 0))
            approved = (
                latest.get("state") == "APPROVED" and latest.get("commit_id") == head
            )
    protected, change_class = None, None
    if files:
        names = [f.get("filename", "") for f in files]
        protected = not any(
            n.startswith((".github/", ".fullsend/", "experiments/", "scripts/"))
            or n in {"AGENTS.md", "CODEOWNERS"}
            for n in names
        )
        if all(n == "docs/example-feature.md" for n in names):
            change_class = "documentation"
    return {
        "AM-CI": ci,
        "AM-REVIEW": approved,
        "AM-FINDINGS": None,
        "AM-RISK": None,
        "AM-CLASS": change_class,
        "AM-PROTECTED": protected,
    }, seen


def observe(number, client=None):
    require(type(number) is int and 0 < number < 1000000, "invalid_pr")
    client = client or Client()
    base = "repos/" + REPOSITORY + "/"
    pr = client.get(base + f"pulls/{number}")
    require(
        pr is not None
        and pr["base"]["repo"]["full_name"] == REPOSITORY
        and pr["base"]["ref"] == "main",
        "unsupported_pr",
    )
    head, target = pr["head"]["sha"], pr["base"]["sha"]
    checks = client.pages(
        base + f"commits/{head}/check-runs?filter=latest", "check_runs"
    )
    reviews = client.pages(base + f"pulls/{number}/reviews")
    files = client.pages(base + f"pulls/{number}/files")
    rules = client.get(base + "rules/branches/main")
    tree = client.get(base + f"git/trees/{target}?recursive=1")
    infrastructure = None
    if tree and not tree.get("truncated"):
        infrastructure = [
            {"path": f["path"], "sha": f["sha"]}
            for f in tree.get("tree", [])
            if f["path"].startswith((".github/", ".fullsend/"))
        ]
    again = client.get(base + f"pulls/{number}")
    rules_again = client.get(base + "rules/branches/main")
    stable = (
        again is not None
        and (
            again["head"]["sha"],
            again["base"]["sha"],
            again["state"],
            again.get("draft"),
        )
        == (head, target, pr["state"], pr.get("draft"))
        and rules == rules_again
    )
    now = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    configuration = digest(
        {"rules": rules, "infrastructure": infrastructure, "base_sha": target}
    )
    ready = {
        "repository": REPOSITORY,
        "branch": "main",
        "configuration_sha256": configuration,
    }
    candidate = dict(ready, head_sha=head, base_sha=target)
    bundle = load_bundle()
    values, seen = normalize(pr, checks, reviews, files)
    readiness = {
        "AR-RULES": bool(rules) if rules is not None else None,
        "AR-CHECKS": checks is not None,
        "AR-REVIEWS": reviews is not None,
        "AR-STATUS": None,
        "AR-TESTS": None,
        "AR-ISOLATION": None,
        "AR-QUEUE": None,
        "AR-HISTORY": None,
    }
    current = stable and pr["state"] == "open" and not pr.get("draft", False)

    def observations(values, who):
        return {
            key: {
                "subject_sha256": digest(who),
                "collected_at": now,
                "trusted_source": bool(current),
                "value": value,
            }
            for key, value in values.items()
            if value is not None
        }

    receipt = qualification(bundle, ready, now, observations(readiness, ready))
    result = gate(
        bundle, candidate, now, observations(values, candidate), "shadow", receipt
    )
    if not current:
        result["decision"] = "hold"
        result["reasons"].append("candidate_not_current_open_pr")
    return {
        "provenance": "read-only-public-github-observation",
        "source_digests": source_digests(),
        "repository": REPOSITORY,
        "pull_request": number,
        "observed_at": now,
        "head_sha": head,
        "base_sha": target,
        "pr_open": pr["state"] == "open",
        "historical_pr_observation": pr["state"] != "open",
        "stable_during_collection": stable,
        "fullsend_review_metadata_present": seen,
        "policy_authority": "native-gemara-prototype-not-approved-standard",
        "review_identity_assurance": "API bot-login metadata, not a production attestation",
        "unimplemented_evidence": [
            "current_fullsend_finding_ledger",
            "trusted_risk_attestation",
            "meaningful_test_sufficiency",
            "runtime_isolation",
            "shadow_track_record",
            "trusted_status_publication",
        ],
        "api_errors": sorted(client.errors),
        "engine": "gemara",
        "qualification": receipt,
        "shadow": result,
        "mutation_permitted": False,
        "authorized_actions": [],
    }


def summary(report):
    """Render only normalized fields; never publish raw API responses."""
    names = {
        "AR-RULES": "Branch rules observable",
        "AR-CHECKS": "Check metadata accessible",
        "AR-REVIEWS": "Review metadata accessible",
        "AR-STATUS": "Trusted status publisher",
        "AR-TESTS": "Meaningful testing",
        "AR-ISOLATION": "Runtime isolation",
        "AR-QUEUE": "Verified merge route",
        "AR-HISTORY": "Shadow track record",
        "AM-CI": "Selected CI checks pass",
        "AM-REVIEW": "Current Fullsend approval",
        "AM-FINDINGS": "No blocking findings",
        "AM-RISK": "Risk within limit",
        "AM-CLASS": "Allowed change class",
        "AM-PROTECTED": "Governed paths untouched",
    }
    lines = [
        "# Gemara shadow trial — no merge authority",
        "",
        f"PR #{report['pull_request']} · head `{report['head_sha']}`",
        "",
        "A successful workflow means evaluation completed, not permission to merge.",
        "Readiness and PR eligibility are separate. Missing evidence remains Unknown.",
        "",
    ]
    lines += [
        f"## Gemara: {report['shadow']['decision']}",
        "",
        "| Scope | Control | Policy / plan | Assessment | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scope, result in [
        ("Repository readiness", report["qualification"]["result"]),
        ("PR candidate", report["shadow"]["evaluation"]),
    ]:
        for row in result["assessments"]:
            lines.append(
                f"| {scope} | {names.get(row['id'], row['id'])} (`{row['id']}`) | {row['policy']} / {row['plan']} | {row['state']} | {row['reason']} |"
            )
    lines += ["", "Hold reasons: " + ", ".join(report["shadow"]["reasons"]), ""]
    lines += [
        "## What this proves",
        "",
        "Real GitHub metadata was assessed through native Gemara catalog requirements and imported Policy assessment plans.",
        "The catalog, policies and generated evaluation logs are schema-validated. GitHub/Fullsend evidence checks are evaluator glue; unsupported policy semantics hold explicitly.",
        "Bot login metadata does not establish a trusted review/finding/risk attestation.",
        "No rules were changed and no merge, comment or status was requested.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Write normalized results to the GitHub job summary",
    )
    args = parser.parse_args()
    try:
        report = observe(args.pr)
        if args.summary:
            Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(summary(report))
        destination = new_output("github")
        (destination / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "repository": REPOSITORY,
                    "pull_request": args.pr,
                    "stable": report["stable_during_collection"],
                    "decision": report["shadow"]["decision"],
                    "mutation_permitted": False,
                    "output": str(destination.relative_to(ROOT)),
                }
            )
        )
        return 0
    except (InputError, ValidationError) as exc:
        code = str(exc)
        if not re.fullmatch(r"[A-Za-z_]{1,80}", code):
            code = "observation_failed"
        print(
            json.dumps({"error": code, "decision": "hold", "mutation_permitted": False})
        )
        return 2
    except (KeyError, TypeError, ValueError, OSError):
        print(
            '{"error":"observation_failed","decision":"hold","mutation_permitted":false}'
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
