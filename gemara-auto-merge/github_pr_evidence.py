#!/usr/bin/env python3
"""Read public PR metadata; never fetch logs, download artifacts or perform writes."""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request

from policy_evaluation import (
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
from result_bundle import write_bundle, write_failure
from fullsend_review_evidence import findings, producer, risk

REPOSITORY = "fullsend-ai/auto-merge"
REPOSITORY_ID = 1383516376
RISK_DISPATCH = {
    "path": "fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@02438e1c117d31bf50f9fb9fafabe40856dbfdda",
    "sha": "02438e1c117d31bf50f9fb9fafabe40856dbfdda",
}
CHECK_NAMES = {"Example contract", "Delayed integration (4 minutes)"}
QUEUE_PROOF_PR = 27
QUEUE_PROOF_RUN = 38665663244
QUEUE_PATHS = {".github/workflows/ci.yml", "scripts/validate_example.py"}


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
        comparison = re.fullmatch(
            re.escape("repos/" + REPOSITORY + "/compare/")
            + r"[0-9a-f]{40}\.\.\.[0-9a-f]{40}\?per_page=20",
            path,
        )
        require(
            path.startswith("repos/" + REPOSITORY + "/")
            and not any(x in path for x in ["\n", "\r", "#", ":"])
            and (".." not in path or comparison is not None),
            "unsupported_endpoint",
        )
        headers = {
            "User-Agent": "gemara-auto-merge-observer",
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
        matching = [r for r in reviews if producer(r)]
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
        protected_names = names + [
            f.get("previous_filename") for f in files if "previous_filename" in f
        ]
        protected = all(
            isinstance(n, str)
            and bool(n)
            and not n.startswith(
                (
                    ".github/",
                    ".fullsend/",
                    "experiments/",
                    "gemara-auto-merge/",
                    "scripts/",
                )
            )
            and n.rsplit("/", 1)[-1] not in {"AGENTS.md", "CODEOWNERS"}
            for n in protected_names
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


def queue_proof(client, base, rules, tree):
    """Historical route proof, invalidated when its CI/validator sources change."""
    absent = {"value": None, "reason": "queue_proof_unavailable"}
    if rules is None or tree is None or tree.get("truncated"):
        return absent
    kinds = {r.get("type") for r in rules}
    required = [r for r in rules if r.get("type") == "required_status_checks"]
    contexts = {
        (c.get("context"), c.get("integration_id"))
        for r in required
        for c in r.get("parameters", {}).get("required_status_checks", [])
    }
    if "merge_queue" not in kinds or not all(
        (n, 15368) in contexts for n in CHECK_NAMES | {"Merge group proof"}
    ):
        return {"value": False, "reason": "queue_rules_not_enforced"}
    pull = client.get(base + f"pulls/{QUEUE_PROOF_PR}")
    run = client.get(base + f"actions/runs/{QUEUE_PROOF_RUN}")
    if not pull or not run:
        return absent
    sha = pull.get("merge_commit_sha")
    if not (
        pull.get("merged") is True
        and pull.get("base", {}).get("ref") == "main"
        and pull.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY
        and re.fullmatch(r"[0-9a-f]{40}", sha or "")
        and run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("head_repository", {}).get("full_name") == REPOSITORY
        and run.get("id") == QUEUE_PROOF_RUN
        and run.get("workflow_id") == 365189945
        and run.get("event") == "merge_group"
        and run.get("path") == ".github/workflows/ci.yml"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("head_sha") == sha
        and (run.get("head_branch") or "").startswith("gh-readonly-queue/main/pr-27-")
    ):
        return {"value": False, "reason": "queue_proof_mismatch"}
    prior = client.get(base + f"git/trees/{sha}?recursive=1")
    if not prior or prior.get("truncated"):
        return absent

    def blobs(snapshot):
        return {
            r["path"]: r["sha"]
            for r in snapshot.get("tree", [])
            if r.get("type") == "blob" and r.get("path") in QUEUE_PATHS
        }

    current, old = blobs(tree), blobs(prior)
    if set(current) != QUEUE_PATHS or current != old:
        return {"value": None, "reason": "queue_proof_configuration_changed"}
    return {
        "value": True,
        "reason": "queue_route_demonstrated",
        "pull_request": QUEUE_PROOF_PR,
        "run_id": QUEUE_PROOF_RUN,
        "head_sha": sha,
    }


RISK_SOURCE_PATHS = {
    ".fullsend/config.yaml",
    ".fullsend/harness/review-gemara.yaml",
    ".fullsend/scripts/post-review-gemara.py",
    ".fullsend/scripts/review-risk.patch",
    ".github/workflows/fullsend.yaml",
}


def local_risk_blobs():
    result = {}
    for name in RISK_SOURCE_PATHS:
        path = ROOT.parent / name
        if not path.is_file() or path.is_symlink():
            return {}
        data = path.read_bytes()
        result[name] = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
    return result


def risk_run_subject(run, receipt, pr):
    """Separate the reviewed revision from the trusted configuration revision."""
    if run.get("event") == "issue_comment":
        return (
            run.get("head_branch") == "main"
            and run.get("head_sha") == receipt["config_sha"]
        )
    if run.get("event") != "pull_request_target" or not isinstance(pr, dict):
        return False
    head, target = pr.get("head") or {}, pr.get("base") or {}
    return (
        (head.get("repo") or {}).get("full_name") == REPOSITORY
        and (target.get("repo") or {}).get("full_name") == REPOSITORY
        and target.get("ref") == "main"
        and target.get("sha") == receipt["config_sha"]
        and head.get("sha") == receipt["head_sha"] == run.get("head_sha")
        and bool(head.get("ref"))
        and head["ref"] == run.get("head_branch")
    )


def risk_suite_subject(suite, run, receipt, pr):
    """Require GitHub's own unambiguous PR/base association for automatic runs."""
    if not isinstance(suite, dict) or not isinstance(pr, dict):
        return False
    linked = suite.get("pull_requests")
    if not isinstance(linked, list) or len(linked) != 1:
        return False
    item = linked[0]
    if not isinstance(item, dict):
        return False
    head, target = item.get("head") or {}, item.get("base") or {}
    return (
        suite.get("id") == run["check_suite_id"]
        and (suite.get("app") or {}).get("id") == 15368
        and suite.get("head_sha") == receipt["head_sha"]
        and suite.get("head_branch") == run["head_branch"]
        and type(pr.get("number")) is int
        and item.get("number") == pr["number"]
        and (head.get("repo") or {}).get("id") == REPOSITORY_ID
        and (target.get("repo") or {}).get("id") == REPOSITORY_ID
        and head.get("sha") == receipt["head_sha"]
        and head.get("ref") == run["head_branch"]
        and target.get("ref") == "main"
        and target.get("sha") == receipt["config_sha"]
    )


def risk_host_history(client, base, configuration, main):
    """Reject changed-and-restored host sources, not only unequal final trees."""
    if not isinstance(main, str) or not re.fullmatch("[0-9a-f]{40}", main):
        return False
    if configuration == main:
        return True
    comparison = client.get(base + f"compare/{configuration}...{main}?per_page=20")
    if not comparison or not (
        comparison.get("status") == "ahead"
        and (comparison.get("base_commit") or {}).get("sha") == configuration
        and (comparison.get("merge_base_commit") or {}).get("sha") == configuration
        and type(comparison.get("total_commits")) is int
        and 0 < comparison["total_commits"] <= 20
    ):
        return False
    commits = comparison.get("commits")
    if not isinstance(commits, list) or len(commits) != comparison["total_commits"]:
        return False
    identifiers = [c.get("sha") for c in commits if isinstance(c, dict)]
    if (
        len(identifiers) != len(commits)
        or any(
            not isinstance(s, str) or not re.fullmatch("[0-9a-f]{40}", s)
            for s in identifiers
        )
        or len(set(identifiers)) != len(commits)
        or main not in identifiers
    ):
        return False
    for identifier in identifiers:
        commit = client.get(base + f"commits/{identifier}?per_page=100")
        files = (commit or {}).get("files")
        if (
            not commit
            or commit.get("sha") != identifier
            or not isinstance(files, list)
            or len(files) >= 100
        ):
            return False
        for file in files:
            if (
                not isinstance(file, dict)
                or not isinstance(file.get("filename"), str)
                or file["filename"] in RISK_SOURCE_PATHS
                or file.get("previous_filename") in RISK_SOURCE_PATHS
            ):
                return False
    return True


def risk_producer(client, base, current_tree, receipt, pr=None, main_sha=None):
    """Bind completed Review execution to its event subject and pinned host sources."""
    endpoint = base + f"actions/runs/{receipt['run_id']}"
    run = client.get(endpoint)
    if not run or not (
        run.get("id") == receipt["run_id"]
        and run.get("run_attempt") == receipt["run_attempt"]
        and run.get("workflow_id") == 365189947
        and run.get("path") == ".github/workflows/fullsend.yaml"
        and risk_run_subject(run, receipt, pr)
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("head_repository", {}).get("full_name") == REPOSITORY
    ):
        return False
    suite_endpoint, suite = None, None
    if run["event"] == "pull_request_target":
        if run.get("referenced_workflows") != [RISK_DISPATCH]:
            return False
        suite_id = run.get("check_suite_id")
        if type(suite_id) is not int or suite_id <= 0:
            return False
        suite_endpoint = base + f"check-suites/{suite_id}"
        suite = client.get(suite_endpoint)
        if not risk_suite_subject(suite, run, receipt, pr):
            return False
        if not risk_host_history(client, base, receipt["config_sha"], main_sha):
            return False
    source_tree = client.get(base + f"git/trees/{receipt['config_sha']}?recursive=1")
    if (
        not current_tree
        or not source_tree
        or current_tree.get("truncated")
        or source_tree.get("truncated")
    ):
        return False

    def blobs(tree):
        return {
            r["path"]: r["sha"]
            for r in tree.get("tree", [])
            if r.get("type") == "blob" and r.get("path") in RISK_SOURCE_PATHS
        }

    current, original = blobs(current_tree), blobs(source_tree)
    if run["event"] == "pull_request_target":
        head_tree = client.get(base + f"git/trees/{receipt['head_sha']}?recursive=1")
        if not head_tree or head_tree.get("truncated") or blobs(head_tree) != original:
            return False
    return (
        set(current) == RISK_SOURCE_PATHS
        and current == original == local_risk_blobs()
        and client.get(endpoint) == run
        and (suite_endpoint is None or client.get(suite_endpoint) == suite)
    )


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
    branch = client.get(base + "branches/main")
    require(
        isinstance(branch, dict)
        and re.fullmatch(r"[0-9a-f]{40}", (branch.get("commit") or {}).get("sha", "")),
        "target_branch_unavailable",
    )
    head = pr["head"]["sha"]
    pr_base_snapshot = pr["base"]["sha"]
    target = branch["commit"]["sha"]
    checks = client.pages(
        base + f"commits/{head}/check-runs?filter=latest", "check_runs"
    )
    reviews = client.pages(base + f"pulls/{number}/reviews")
    comments = client.pages(base + f"issues/{number}/comments")
    files = client.pages(base + f"pulls/{number}/files")
    rules = client.get(base + "rules/branches/main")
    tree = client.get(base + f"git/trees/{target}?recursive=1")
    queue = queue_proof(client, base, rules, tree)
    finding_evidence = findings(head, reviews, comments)
    risk_evidence = risk(
        head,
        reviews,
        comments,
        lambda data: risk_producer(client, base, tree, data, pr, target),
    )
    infrastructure = None
    if tree and not tree.get("truncated"):
        infrastructure = [
            {"path": f["path"], "sha": f["sha"]}
            for f in tree.get("tree", [])
            if f["path"].startswith((".github/", ".fullsend/"))
        ]
    reviews_again = client.pages(base + f"pulls/{number}/reviews")
    comments_again = client.pages(base + f"issues/{number}/comments")
    checks_again = client.pages(
        base + f"commits/{head}/check-runs?filter=latest", "check_runs"
    )
    rules_again = client.get(base + "rules/branches/main")
    branch_again = client.get(base + "branches/main")
    again = client.get(base + f"pulls/{number}")
    stable = (
        again is not None
        and (
            again["head"]["sha"],
            again["base"]["sha"],
            again["state"],
            again.get("draft"),
        )
        == (head, pr_base_snapshot, pr["state"], pr.get("draft"))
        and rules == rules_again
        and branch_again is not None
        and (branch_again.get("commit") or {}).get("sha") == target
        and reviews == reviews_again
        and comments == comments_again
        and checks == checks_again
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
    values["AM-FINDINGS"] = finding_evidence["value"]
    values["AM-RISK"] = risk_evidence["value"]
    readiness = {
        "AR-RULES": bool(rules) if rules is not None else None,
        "AR-CHECKS": checks is not None,
        "AR-REVIEWS": reviews is not None,
        "AR-STATUS": None,
        "AR-TESTS": None,
        "AR-ISOLATION": None,
        "AR-QUEUE": queue["value"],
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
        "github_pr_base_snapshot_sha": pr_base_snapshot,
        "pr_open": pr["state"] == "open",
        "historical_pr_observation": pr["state"] != "open",
        "stable_during_collection": stable,
        "fullsend_review_metadata_present": seen,
        "policy_authority": "native-gemara-prototype-not-approved-standard",
        "review_identity_assurance": "Pinned API bot ID/login/type, not a signed production attestation",
        "evidence_details": {
            "AM-FINDINGS": finding_evidence,
            "AM-RISK": risk_evidence,
            "AR-QUEUE": queue,
            "AR-TESTS": {
                "value": None,
                "reason": "toy_validator_is_not_test_sufficiency_approval",
            },
            "AR-ISOLATION": {
                "value": None,
                "reason": "runtime_isolation_assurance_not_attested",
            },
            "AR-HISTORY": {
                "value": None,
                "reason": "shadow_outcomes_and_promotion_criteria_not_accepted",
            },
            "AR-STATUS": {
                "value": None,
                "reason": "observer_is_read_only_not_an_authoritative_publisher",
            },
        },
        "readiness_evidence_required": [
            "owner_accepted_test_sufficiency",
            "runtime_isolation_assurance",
            "owner_accepted_shadow_outcomes",
            "authoritative_status_publisher",
        ],
        "api_errors": sorted(client.errors),
        "engine": "gemara",
        "candidate_decision": result["evaluation"]["decision"],
        "readiness_decision": receipt["decision"],
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
        f"PR candidate: **{report['candidate_decision']}** · repository readiness: **{report['readiness_decision']}** · combined gate: **{report['shadow']['decision']}**.",
        "Candidate eligibility is an advisory policy result, never merge permission.",
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
        "Finding evidence uses the official v2 ledger, pinned bot identity, explicit head marker and matching approval; it is not a signed production attestation.",
        "No rules were changed and no merge, comment or status was requested.",
    ]
    lines += ["", "## Evidence collection details", ""]
    for control, detail in report["evidence_details"].items():
        lines.append(f"- `{control}`: `{detail['reason']}`")
    lines += [
        "",
        "The lab risk receipt must bind a completed Fullsend run, its attempt, the exact reviewed head and the current pinned host sources. Automatic pull_request_target runs also bind the PR head branch and base configuration commit; issue_comment runs bind the main configuration commit. Meaningful tests, runtime isolation, a trusted eligibility publisher and an accepted shadow history need independent evidence; neither approval nor a successful queue run proves them.",
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
            Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
                summary(report)
                + "\nDownload this job's `gemara-evaluation` artifact for native logs, normalized evidence, effective policy and a digest manifest.\n"
            )
        write_bundle(
            {
                k: report[k]
                for k in ["repository", "pull_request", "head_sha", "base_sha"]
            },
            {
                "readiness": report["qualification"]["result"],
                "candidate": report["shadow"]["evaluation"],
            },
            {"repository": load_bundle()},
            report["shadow"]["decision"],
            report["readiness_decision"],
            "shadow",
        )
        destination = new_output("github")
        (destination / "pr-evidence-and-policy-report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "repository": REPOSITORY,
                    "pull_request": args.pr,
                    "stable": report["stable_during_collection"],
                    "decision": report["shadow"]["decision"],
                    "candidate_decision": report["candidate_decision"],
                    "readiness_decision": report["readiness_decision"],
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
        write_failure(code, "shadow")
        print(
            json.dumps({"error": code, "decision": "hold", "mutation_permitted": False})
        )
        return 2
    except (KeyError, TypeError, ValueError, OSError):
        write_failure("observation_failed", "shadow")
        print(
            '{"error":"observation_failed","decision":"hold","mutation_permitted":false}'
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
