# Gemara auto-merge

One engine: native Gemara. The comparison evaluator and custom JSON rule profiles
have been removed. Start with the [walkthrough](../docs/attempts/02-policy-evaluation/SHADOW-OBSERVATION.md).
The replay and shadow observer remain read-only. A separate, explicitly granted
[live pilot](../docs/attempts/02-policy-evaluation/DOCUMENTATION-AUTO-MERGE-PILOT.md) has demonstrated
protected-queue merges; the one-shot grant has been replaced by a bounded repository pilot configuration
and exact-head maintainer maintenance path.

## File guide

- **`catalogs/` — what must be true.** The repository-readiness catalog covers
  readiness and PR eligibility; the documentation catalog covers the bounded
  auto-merge pilot. The maintainer-approved catalog is retained for a disabled path.
- **`policies/` — how requirements are assessed.** Common policy and repository
  policy are combined for PR eligibility; documentation auto-merge policy adds the
  live pilot checks. The maintainer-approved policy stays disabled.
- **`config/documentation-auto-merge-settings.json` — owner-controlled pilot settings.**
  Contains enablement, expiry and allowed documentation paths; it is not a Gemara Policy.
- **`config/temporary-merge-writer-app-manifest.json` — temporary GitHub App registration.**
  Describes requested permissions; it contains no key or installation token.
- **`native-evaluator/` — Go code that executes Gemara assessments.**
  Conventional Go filenames remain inside this directory.
- **`policy_evaluation.py` — load policies, bind evidence and interpret results.**
- **`github_pr_evidence.py` / `fullsend_review_evidence.py` — collect and verify evidence.**
- **`authorize_auto_merge.py` — evaluate authorization for queue entry or queue validation.**
- **`resolve_pr_from_event.py` — resolve a PR from trusted workflow event metadata.**
- **`github_app_token_scope.py` — verify that the temporary App token is repository-scoped.**
- **`run_policy_examples.py` / `verify_recorded_trial_evidence.py` — synthetic examples
  and read-only checks of the recorded live trial PRs.**
- **`toolchain-lock.json`, `install_pinned_toolchain.py`, `build_native_evaluator.py` —
  pin, install and build the evaluator and official schema validator.**
  Generated `evaluator-build-lock.json` and reports under `out/` remain ignored.
- **`test_*.py` — tests named after the component or behavior they verify.**

Workflow entry points live in `.github/workflows/`:
`gemara-shadow-observation.yml` observes without merging;
`gemara-auto-merge.yml` evaluates a PR for the bounded live pilot;
`gemara-queue-writer.yml` performs the scoped App-backed queue request; and
`gemara-merge-queue.yml` validates the queued revision. The required check name
`Gemara pilot queue gate` is intentionally unchanged to preserve branch-rule bindings.

This directory replaces `experiments/autonomy-platform/`. Artifact IDs and control
IDs remain stable so earlier evaluation records still identify the same requirements;
file paths and human-readable titles now describe their purpose.

## What to read

- [repository-readiness-and-pr-controls.json](catalogs/repository-readiness-and-pr-controls.json): native ControlCatalog defining readiness
  and PR-candidate requirements.
- [common-auto-merge-policy.json](policies/common-auto-merge-policy.json): native Policy importing that
  catalog and binding requirements to named automated assessment methods.
- [repository-auto-merge-policy.json](policies/repository-auto-merge-policy.json): native Policy importing
  the common policy and adding a documentation-only requirement for this lab.
- `native-evaluator/policy_assessment.go`: resolves these imports, scope and assessment plans using native
  Gemara types; binds supported method names to executable checks.
- `native-evaluator/main.go`: executes native SDK assessments/evidence collection/aggregation
  and emits a native EvaluationLog, including catalog, requirement and policy-plan
  references. The host validates that log before using its result.
- `github_pr_evidence.py`: reads GitHub metadata and supplies bounded observations.

JSON is a supported Gemara artifact format; these files are not a Fullsend policy
language. Policies name the requirements and parameters; the evaluator still
implements what GitHub CI, Fullsend approval and other evidence mean. Gemara does
not interpret arbitrary prose as executable checks. See [upstream policy authoring](https://gemara.openssf.org/tutorials/policy/policy-guide).

## Run

Requires Python 3.11+ and Go 1.25+; CI pins Go 1.26.6.

```sh
python3 gemara-auto-merge/install_pinned_toolchain.py
python3 gemara-auto-merge/build_native_evaluator.py
python3 -m unittest discover -s gemara-auto-merge -p 'test_*.py'
python3 gemara-auto-merge/run_policy_examples.py
python3 gemara-auto-merge/github_pr_evidence.py --pr 28
```

Setup downloads hash-pinned CUE/schema data and checksum-pinned Go modules. Use
`build_native_evaluator.py --offline` after dependency setup. Build/evaluator/validator children
receive clean environments without forge credentials. Tools, build receipts and
reports are ignored; schema source is downloaded into `.tools/`, not vendored in Git.

The replay uses explicitly synthetic evidence. Its cases cover satisfied, failed,
missing, stale, wrong-revision and stricter repository-policy outcomes. Off does
not evaluate; Shadow/Gemara simulate policy decisions; Light additionally limits
change class to dependency digests. This repository's policy permits documentation
only, so Light holds here. None of those simulations enables a real merge.
`run_policy_examples.py --write-report` saves complete native logs in ignored `out/`.

The observer is fixed to public `fullsend-ai/auto-merge` and `main`. It makes
bounded GET-only requests, refuses redirects and holds on incomplete/changing
state. It never executes PR code, reads workflow logs, posts
comments/statuses or changes rules. An approved read credential can be supplied
locally via GH_TOKEN/GITHUB_TOKEN when needed; it is not passed to the evaluator.
Reports discard API bodies, patches, review text and actor identities. The collector
uses the official v2 findings projection with a pinned bot ID, explicit head and
matching approval; any open finding holds. It verifies a historical queue route
against current rules and CI/validator source hashes. Reviews, comments and CI
are rechecked for collection stability. Only normalized control results and source
identifiers enter reports. The legacy risk comment lacks revision binding and cannot satisfy the risk
control. The lab now composes the pinned official Review harness with a small
host publication extension: it emits a sanitized head/config/run/attempt-bound
risk receipt. The collector verifies a completed Fullsend run using event-specific
bindings: `issue_comment` identifies the main configuration commit, while a
same-repository `pull_request_target` run identifies the PR head separately from
its base configuration using GitHub's unambiguous check-suite PR/base association
and pinned dispatcher reference. Current/configuration host source blobs must match the
pins; automatic reviews also require matching host sources at the PR head before
supplying ordinal risk to Gemara. This is
a lab receipt contract, not an upstream feature or a new model agent. See the
[evidence update](../docs/attempts/02-policy-evaluation/SHADOW-OBSERVATION.md#evidence-and-trust-boundaries)
for verified sources and the remaining evidence owners.

The `Gemara shadow observation` workflow runs trusted main code after
CI, and after Fullsend runs when GitHub associates a PR. Manual dispatch on main
with a PR number handles Review commands that have no associated PR in the
workflow event. The Summary lists each native policy/plan and its result. A green
workflow means evaluation completed; read the decision, which can still hold.
The Gemara integration-test job in CI uses synthetic data only. Neither path installs
merge rules or publishes an authoritative eligibility check.

## Supported policy semantics

This evaluator handles the configured auto-merge use case, not every possible
Gemara application. It resolves local policy/catalog references with exact artifact
versions, rejects cycles/unresolved references, checks scope, applies catalog
exclusions, and requires executable coverage of every imported applicable
requirement. Imported policy assessments remain mandatory: child plans add to
rather than replace them. A looser child cannot erase a failed common assessment.

Scope values are OR within a dimension and AND across dimensions, with exclusions
applied afterward. `technologies` and `groups` map to the GitHub platform and
repository; missing context for other dimensions holds. Named Intent/Automated
methods support risk limits, change classes and a maximum evidence age up to 600
seconds. Unknown methods, manual methods, prose constraints, requirement
modifications, risk acceptances/mitigations, implementation timelines, guidance
imports and enforcement actions produce an explicit error/hold. They are not
silently ignored or represented as implemented. No policy URL is fetched or run.

The official schema pin is Gemara **v1.5.0**. The tested Go SDK is separately pinned at **v0.11.1-0.20261009030221-5e33fda460a8**, which advertises schema compatibility with that version. Schema and
binary hashes are pinned in `toolchain-lock.json`; the tested SDK module is pinned in
`native-evaluator/go.mod`. We do not round-trip native Policy structs or claim v1.6 compatibility.
Input documents and every generated EvaluationLog must pass official validation.

Readiness and candidate results bind the repository configuration and exact
candidate revision to hashes of the native policy bundle. Receipts are local and
unsigned. Bot approval alone is not a finding/risk attestation. The findings
projection has its own source checks; it is not a signed production receipt. Missing
readiness assurance, findings or risk still holds even with green CI and approval.
This remains a prototype, not an approved company standard or a production merger.


## Verify the complete live shadow example

After the configured official Review finishes for PR #28:

```sh
python3 gemara-auto-merge/verify_recorded_trial_evidence.py
```

Or dispatch `Gemara shadow observation` on main with `pr=28` and
`verify_example=true`. It verifies PR #28 passes every native candidate assessment,
PR #29's intentional CI failure holds, and neither candidate overrides missing
repository readiness. The workflow needs actions:read only to verify producer run
metadata; it neither reads workflow logs nor downloads result artifacts.

A successful example is not an autonomous-merge qualification. Candidate policy,
repository readiness and the combined gate are reported separately. Readiness
requirements still need accepted test-sufficiency, runtime-isolation and shadow
outcome evidence, plus an authoritative publisher. Unknown evidence stays Unknown;
the fully supplied readiness case remains explicitly synthetic in run_policy_examples.py. No
production threshold or approval is invented from the two test PRs.

## Repeatable pilot and maintenance

See [documentation-auto-merge-settings.json](config/documentation-auto-merge-settings.json) and the
[live walkthrough](../docs/attempts/02-policy-evaluation/DOCUMENTATION-AUTO-MERGE-PILOT.md).
The common and repository policies still govern automatic candidates; the separate
maintenance policy remains disabled for the demo. Its retained documentation-only
path requires explicit execution and independent current-head human approval;
governance paths require code-owner review. The draft writer uses a dedicated temporary repository App with a main-only
Actions environment. Fullsend-native token minting remains unresolved.
This draft does not depend on an unmerged upstream workflow or a personal token.

## Evidence publication and current proof

The dedicated lab App completed [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41)
without a manual queue retry. Production readiness still holds; see the
[current implementation report](../docs/attempts/02-policy-evaluation/D1-D4-REPORT.md).

`result_bundle.py` exports native logs, normalized observation evidence, effective
policy, a subject-bound decision, summary and digest manifest from the existing
shadow/enrollment/queue workflows. Artifacts are retained for 14 days. Reports
contain no raw forge response, model prose or environment dump. A digest manifest
is an unsigned integrity record, not an independent trust attestation.

The [Review contract](../docs/attempts/02-policy-evaluation/REVIEW-EVIDENCE-CONTRACT.md)
explains the repository-local Fullsend binary experiment. Its source overlay and
build/replay recipes live here; generated binaries stay ignored. It uses synthetic
host inputs and publication proof to test the contract through real Fullsend and
Gemara execution. It does not enable a new live Review publisher or replace the
existing verified bot/risk-receipt consumer.

## Hosted vendored Review

[The vendored-mode trial](../docs/attempts/02-policy-evaluation/HOSTED-VENDORED-REVIEW.md)
installs the official local workflows/defaults and the built binary, rather than
merely storing a binary for local replay. `native_review_artifacts.py` reads only
a bounded, digest-checked native Review JSON artifact from authenticated Actions
execution; it does not read arbitrary artifacts or workflow logs. Native record
absence fails closed once the vendored host lock is present.
