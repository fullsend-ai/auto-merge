# Auto-Merge agent implementation

Status: observe-only POC aligned with Fullsend ADR 0110; the earlier lab proved
an exact-head merge, but mutation is now deliberately disabled pending the
production authority controls

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
3. A trusted runner post-script records an Actions-log preview and refreshes
   every mutable fact. This POC never calls a GitHub mutation endpoint.

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
The current policy mode is `observe`. Production should replace `coder` with a
purpose-built identity and split read/observe capability from the narrowly
constrained live merge driver.

## Deterministic preflight

`.fullsend/scripts/pre-auto-merge.sh` invokes
`.fullsend/scripts/auto_merge_gate.py` before Fullsend creates the sandbox. The
gate obtains current state through `gh api` and requires:

- target repository exactly `ascerra/auto-merge`;
- open, non-draft pull request with known `mergeable: true` and
  `mergeable_state: clean`;
- head repository equal to base repository, so forks are excluded;
- base ref exactly `main`;
- author in the explicit POC allowlist (`ascerra` or the Fullsend bots);
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
mode
policy_fingerprint
context_fingerprint
```

`policy_fingerprint` hashes canonical policy state, including mode and cohort
controls. `context_fingerprint` hashes the complete canonical evidence after
its context-fingerprint fields are removed. The post-script recomputes both
before trusting the evidence. No token, credential, raw workflow environment,
or complete event payload enters the document.

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

## Observe record

After Fullsend's validation loop accepts the model JSON, the post-script invokes
`.fullsend/scripts/auto_merge_finalize.py`. It verifies both fingerprints,
eligibility, schema-level fields, exact binding, and the APPROVE/risk invariant.
It emits decision and outcome previews to the Actions log. Observe mode makes no
pull-request comment, merge, queue, label, or other GitHub mutation.

## Authoritative postflight

For `APPROVE`, the finalizer runs the same gate again against live GitHub state
using the same policy. It requires the fresh result to remain eligible and the
repository, pull request, head SHA, base ref, base SHA, and policy fingerprint
to match the original binding. The fresh context fingerprint may differ because
capture time and non-binding observations are new; its own canonical hash must
still be valid.

If eligibility or binding changed, the script records a stale-decision outcome
and exits successfully without merging. It never retries using the old
decision and never falls back to a less precise mutation.

## Live mutation is intentionally absent

The POC accepts only `AUTO_MERGE_MODE=observe`; parser and trusted postflight
reject every other value. The finalizer contains no GitHub mutation helper or
merge call. The earlier private-lab run remains evidence that expected-head
merging works, but live code must not return until Fullsend owns a per-PR lease,
idempotency key, durable pending receipt, timeout reconciliation, constrained
forge driver, and queue-aware operation.

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
- The reusable Fullsend workflow loads custom harness configuration from
  `github.event.pull_request.base.sha`. For long-lived PRs this can be stale;
  run #99 loaded `307b6f9` even though the workflow itself ran from
  `main@5975b78`. Production dispatch must use current trusted base-branch
  configuration while preserving the untrusted-head boundary.
- Observe mode still executes on a runner whose hosted `coder` identity is
  broader than the eventual observer identity. Code prevents mutations, but
  capability separation must be enforced by credentials in production.
