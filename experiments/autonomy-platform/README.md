# Native Gemara autonomy trial

One engine: native Gemara. The comparison evaluator and custom JSON rule profiles
have been removed. Start with the [walkthrough](../../docs/attempts/02-policy-evaluation/LIVE-TRIAL.md).
Every mode remains a read-only experiment; no result grants merge authority.

## What to read

- [controls.json](policies/controls.json): native ControlCatalog defining readiness
  and PR-candidate requirements.
- [common-policy.json](policies/common-policy.json): native Policy importing that
  catalog and binding requirements to named automated assessment methods.
- [repository-policy.json](policies/repository-policy.json): native Policy importing
  the common policy and adding a documentation-only requirement for this lab.
- `sdk/policy.go`: resolves these imports, scope and assessment plans using native
  Gemara types; binds supported method names to executable checks.
- `sdk/main.go`: executes native SDK assessments/evidence collection/aggregation
  and emits a native EvaluationLog, including catalog, requirement and policy-plan
  references. The host validates that log before using its result.
- `github_observe.py`: reads GitHub metadata and supplies bounded observations.

JSON is a supported Gemara artifact format; these files are not a Fullsend policy
language. Policies name the requirements and parameters; the evaluator still
implements what GitHub CI, Fullsend approval and other evidence mean. Gemara does
not interpret arbitrary prose as executable checks. See [upstream policy authoring](https://gemara.openssf.org/tutorials/policy/policy-guide).

## Run

Requires Python 3.11+ and Go 1.25+; CI pins Go 1.26.6.

```sh
python3 experiments/autonomy-platform/bootstrap_tools.py
python3 experiments/autonomy-platform/build_sdk.py
python3 -m unittest discover -s experiments/autonomy-platform -p 'test_*.py'
python3 experiments/autonomy-platform/demo.py
python3 experiments/autonomy-platform/github_observe.py --pr 28
```

Setup downloads hash-pinned CUE/schema data and checksum-pinned Go modules. Use
`build_sdk.py --offline` after dependency setup. Build/evaluator/validator children
receive clean environments without forge credentials. Tools, build receipts and
reports are ignored; schema source is downloaded into `.tools/`, not vendored in Git.

The replay uses explicitly synthetic evidence. Its cases cover satisfied, failed,
missing, stale, wrong-revision and stricter repository-policy outcomes. Off does
not evaluate; Shadow/Gemara simulate policy decisions; Light additionally limits
change class to dependency digests. This repository's policy permits documentation
only, so Light holds here. None of those simulations enables a real merge.
`demo.py --write-report` saves complete native logs in ignored `out/`.

The observer is fixed to public `fullsend-ai/auto-merge` and `main`. It makes
bounded GET-only requests, refuses redirects and holds on incomplete/changing
state. It never executes PR code, downloads artifacts, reads workflow logs, posts
comments/statuses or changes rules. An approved read credential can be supplied
locally via GH_TOKEN/GITHUB_TOKEN when needed; it is not passed to the evaluator.
Reports discard API bodies, patches, review text and actor identities.

The `Autonomy shadow observation` workflow runs trusted main code after
CI, and after Fullsend runs when GitHub associates a PR. Manual dispatch on main
with a PR number handles Review commands that have no associated PR in the
workflow event. The Summary lists each native policy/plan and its result. A green
workflow means evaluation completed; read the decision, which can still hold.
The separate fixture workflow uses synthetic data only. Neither workflow installs
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

SDK and official schemas are deliberately matched at Gemara **v1.5.0**. Schema and
binary hashes are pinned in `tool-lock.json`; the tested SDK module is pinned in
`sdk/go.mod`. We do not round-trip native Policy structs or claim v1.6 compatibility.
Input documents and every generated EvaluationLog must pass official validation.

Readiness and candidate results bind the repository configuration and exact
candidate revision to hashes of the native policy bundle. Receipts are local and
unsigned. Bot approval metadata is not a full finding/risk attestation. Missing
readiness assurance, findings or risk still holds even with green CI and approval.
This remains a prototype, not an approved company standard or a production merger.
