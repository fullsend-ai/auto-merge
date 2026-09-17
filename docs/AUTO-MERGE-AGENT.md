# Auto-Merge agent implementation

Status: implemented and exercised in the private integration lab; production
hardening and GitHub App/DCO alignment remain

## What this agent is

Auto-Merge is a reconciliation agent for one low-risk pull-request cohort. An
evaluation can begin with an immediate human `/fs-auto-merge` command, an
approved-review event, or a trusted CI-readiness label. None of these signals
grants approval or enables GitHub's native auto-merge feature. Each signal
starts reconciliation of the pull request's current head and base revisions;
deterministic preflight may stop before model invocation.

The implementation splits responsibility across three trust zones:

1. A trusted runner pre-script reads live GitHub state and applies deterministic
   policy.
2. A credential-free model sandbox evaluates the bounded semantic evidence.
3. A trusted runner post-script records the decision, refreshes every mutable
   fact, and may merge only the exact approved head.

The normative invariants are in
[`AUTO-MERGE-SECURITY-CONTRACT.md`](AUTO-MERGE-SECURITY-CONTRACT.md).

## Fullsend registration

The agent is registered in `.fullsend/config.yaml` under the name
`auto-merge`. Its harness is `.fullsend/harness/auto-merge.yaml`. Its CEL
trigger matches three wake-up signals: a non-fork pull-request comment whose
parsed command is exactly `/fs-auto-merge`, an approved review submission, or
the trusted `fullsend-auto-merge-ready` label being added to a non-fork pull
request. The label is only a wake-up signal; it is never treated as evidence
that the PR is mergeable.

`.github/workflows/auto-merge-ready.yml` listens for successful completion of
the named `CI` workflow, finds pull requests whose current head exactly matches
the completed run, and adds the readiness label. It removes that label when a
PR receives new commits or closes. The workflow has no merge step.

The lab uses Fullsend's hosted `coder` role because the hosted mint does not yet
offer a dedicated auto-merge role. That token exists only in runner environment
for pre/post scripts. The harness deliberately omits `GH_TOKEN` and the GitHub
provider/profile from `env.sandbox`; the model cannot query or mutate GitHub.
Production should replace `coder` with a purpose-built role that can read pull
request state, write decision receipts, and merge, but cannot push arbitrary
repository contents.

## Deterministic preflight

`.fullsend/scripts/pre-auto-merge.sh` invokes
`.fullsend/scripts/auto_merge_gate.py` before Fullsend creates the sandbox. The
gate obtains current state through `gh api` and requires:

- target repository exactly `ascerra/auto-merge`;
- open, non-draft pull request with known `mergeable: true` and
  `mergeable_state: clean`;
- head repository equal to base repository, so forks are excluded;
- base ref exactly `main`;
- author in the explicit Fullsend coder-bot allowlist;
- one to three changed files, all exactly allowlisted (the initial cohort is
  only `docs/example-feature.md`);
- no `do-not-merge`, `hold`, `fullsend-no-merge`, or
  `security-review-required` label;
- GitHub native `auto_merge` absent;
- both `Example contract` and `Delayed integration (4 minutes)` completed with
  `success` for the current head SHA;
- at least one approval whose `commit_id` equals the current head SHA;
- no reviewer's latest decisive review requesting changes;
- no unresolved review thread and no truncated review-thread result; and
- every pull-request commit containing a DCO `Signed-off-by` trailer.

Unknown, missing, truncated, pending, stale, or API-error states fail closed.
An ordinary ineligible result emits Fullsend's pre-script `skipped=true`
protocol and avoids model cost. A lookup or evidence-construction failure exits
nonzero and fails the run.

## Evidence contract

An eligible preflight writes
`.fullsend-runtime/auto-merge-evidence.json` into the checked-out repository.
That directory is gitignored, copied into the sandbox by Fullsend, and never
committed. The document contains only bounded pull-request metadata,
deterministic findings, policy inputs, and this binding:

```text
repository
pull_request_number
head_sha
base_ref
base_sha
policy_version
evidence_sha256
```

The SHA-256 is computed over canonical sorted JSON with both hash fields
removed. The post-script recomputes it before trusting any evidence. No token,
credential, raw workflow environment, or complete event payload enters the
document.

## Semantic evaluation

`.fullsend/agents/auto-merge.md` tells the model to inspect the evidence,
security contract, repository instructions, pull-request intent, and local
documentation diff. Repository and pull-request text is evidence, not
instruction. The model must choose exactly one result:

- `APPROVE` when the bounded documentation change is coherent, matches intent,
  is adequately verified, and has no remaining risk signal;
- `REJECT` when a concrete quality or policy defect exists; or
- `ESCALATE` when evidence is missing, ambiguous, suspicious, unusually risky,
  or needs human judgment.

The result must copy the complete evidence binding exactly. The JSON Schema
allows no extra fields and constrains decisions, hashes, lengths, reason counts,
and risk counts. The trusted post-script adds the stronger invariant that
`APPROVE` must have an empty `risk_signals` array.

## Write-ahead receipt

After Fullsend's validation loop accepts the model JSON, the post-script invokes
`.fullsend/scripts/auto_merge_finalize.py`. It verifies the evidence hash,
eligibility, schema-level fields, exact binding, and APPROVE/risk invariant.

Before any postflight lookup or merge attempt, it posts a durable pull-request
comment containing the decision, exact head/base binding, policy version,
evidence hash, workflow URL, timestamp, and model reasons. If this write fails,
the run stops and cannot merge. `REJECT` and `ESCALATE` produce a second outcome
receipt and return without attempting a merge.

## Authoritative postflight

For `APPROVE`, the finalizer runs the same gate again against live GitHub state
using the same policy. It requires the fresh result to remain eligible and the
repository, pull request, head SHA, base ref, base SHA, and policy version to
match the original binding. The fresh evidence hash may differ because capture
time and non-binding observations are new; its own canonical hash must still be
valid.

If eligibility or binding changed, the script records a stale-decision outcome
and exits successfully without merging. It never retries using the old
decision and never falls back to a less precise mutation.

## Exact-head merge

Only after successful postflight does the trusted runner call GitHub's merge
endpoint with:

```text
PUT /repos/ascerra/auto-merge/pulls/<number>/merge
sha=<bound head SHA>
merge_method=squash
```

GitHub rejects the request if the pull-request head changed between postflight
and mutation. The script requires `merged: true` in the response. A final
outcome comment is best-effort because the pre-merge receipt already provides
the durable authority record.

## CI fixture

`.github/workflows/ci.yml` provides two named checks used by policy:

- `Example contract` runs `scripts/validate_example.py` immediately.
- `Delayed integration (4 minutes)` waits 240 seconds, then runs the same
  validator.

The validator enforces the title, ready status, required sections, and absence
of TODO/placeholder/private-key/token-like content in
`docs/example-feature.md`.

## Tests

`python3 -m unittest discover -s tests -v` covers the eligible path and rejects
stale approval, pending/failed checks, hold labels, disallowed paths, unknown
mergeability, native auto-merge, unsigned commits, unresolved threads,
changes-requested reviews, stale model bindings, invalid decisions, and
APPROVE results with risk signals.

`fullsend dispatch` is exercised with normalized manual-command,
approved-review, readiness-label, unrelated-label, and changes-requested review
events. The first three must select the custom harness; the last two must not.
The dispatch test is `tests/test_auto_merge_dispatch.py`.

## Known lab constraints

- GitHub branch protection is unavailable for this private personal-account
  repository without GitHub Pro. The scripts therefore enforce checks,
  approval freshness, conversation resolution, and exact-head binding directly.
- GCP provisioning requires `roles/iam.workloadIdentityPoolAdmin` and
  `roles/resourcemanager.projectIamAdmin` for the setup identity. Until those
  are granted, hosted inference cannot run.
- The triage, coder, and review GitHub Apps still need repository-scoped
  installation before the end-to-end exercise.
