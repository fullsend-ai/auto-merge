# Fullsend Auto-Merge: Design, Private Lab, Evidence, and Lessons

Document type: NotebookLM source document

Status: Private lab complete; production design gaps remain

Lab repository: `ascerra/auto-merge`

Date completed: September 17, 2026; final automatic-path proof added September 22, 2026

## Purpose of this document

This document is a self-contained source for studying the Fullsend Auto-Merge
design in NotebookLM. It explains the problem, the authority boundary, the
private-repository experiment, the successful and unsuccessful cases, the
risks of relying only on a forge's native "merge when ready" button, the
evidence produced by the lab, and the work still needed for production.

The content is included directly because the GitHub repository and many of the
evidence links are private. NotebookLM does not need access to those links to
understand the design or the lab results.

## Executive summary

We built and proved a custom Fullsend Auto-Merge agent in a new private GitHub
repository. The agent merges only when deterministic forge state and a bounded
semantic assessment agree that one exact pull-request revision is eligible.

The model is advisory. It can return `APPROVE`, `REJECT`, or `ESCALATE`, but it
does not receive a GitHub credential and cannot merge anything. Trusted code
collects evidence, enforces deterministic policy, writes a durable decision
receipt, repeats every mutable check immediately before mutation, and performs
an exact-head compare-and-swap merge.

The complete exercise succeeded:

- Fullsend was installed in per-repository mode.
- Workload identity trusted only `ascerra/auto-merge`.
- The public Fullsend mint was not changed.
- `/fs-triage` processed a real issue.
- The code agent created a real pull request.
- Review and Fix ran against the pull request.
- A fast CI check and a deliberately delayed four-minute check passed.
- The first Auto-Merge run safely escalated because semantic patch evidence was
  missing.
- A later automatic-path run on PR #7 passed preflight, produced a bound
  semantic `APPROVE`, wrote pending and merged receipts, and squash-merged the
  exact approved head without a human command.
- The evidence contract was strengthened.
- The final Auto-Merge run approved and squash-merged the exact expected head.
- Twenty-seven Auto-Merge unit tests and the full local validation suite passed.

The core lesson is that Auto-Merge should be a reconciliation controller, not
standing permission to merge a future revision.

## The problem being solved

A pull request can appear ready while still carrying subtle uncertainty:

- CI may be running, missing, stale, or associated with another head SHA.
- An approval may apply to an older revision.
- A review thread or changes-requested review may remain unresolved.
- The pull request may have moved to a different base revision.
- The patch may not match the issue even though tests pass.
- A hold label or policy-denied file may make the change ineligible.
- The model may be missing the actual patch and therefore lack enough evidence.
- State may change after a semantic decision but before the merge request.
- A forge response may time out after the mutation succeeds, leaving the
  controller uncertain about the outcome.

A safe system must separate deterministic facts from semantic judgment and
must keep merge authority outside the model sandbox.

## Design principles

### 1. The model is advisory

The model answers only the non-deterministic question: does this bounded patch
match the stated intent, remain routine and coherent, have meaningful tests,
and avoid risks that require human judgment?

The model does not establish authoritative forge facts. It cannot decide that
CI passed, that an approval is current, or that a head SHA has not changed.
Those are trusted deterministic checks.

### 2. Authorization applies to one exact tuple

Every semantic decision is bound to:

```text
(repository,
 pull_request_number,
 head_sha,
 base_ref,
 live_base_sha,
 policy_fingerprint)
```

The evaluated evidence is separately bound by `context_fingerprint`. Changing
any authority-tuple element or the context fingerprint invalidates the
decision. A model approval for one binding does not authorize another head,
base, repository, pull request, policy, or evidence document.

### 3. Readiness is checked before model invocation

The workflow is event-driven, but model invocation is readiness-driven. An
early event may trigger reconciliation while CI is still pending. The trusted
preflight should cheaply detect that state and stop without spending inference.

### 4. The decision is recorded before authority is exercised

The trusted runner writes a durable decision receipt before attempting a merge.
This is a write-ahead record of the exact authority transition being attempted.

### 5. Every mutable fact is checked again

Immediately before mutation, trusted postflight recollects forge state and
repeats every mutable gate. A changed head, base, check, review, label, thread,
or mergeability result causes a stale-decision rejection.

### 6. The mutation is exact-head and fail-closed

The merge request supplies the expected head SHA. If the forge reports that the
head changed, the controller records the stale outcome and waits for a new
event. It does not fall back to a less precise merge command.

### 7. There is one Auto-Merge enablement path

The design intentionally does not preserve the legacy `CODE_AUTO_MERGE` path.
Maintaining two independent ways to grant merge authority is too dangerous.
The dedicated Auto-Merge agent is the single enablement path.

## High-level state machine

```text
event
  -> trusted deterministic preflight
     -> ineligible
        -> record reason
        -> stop before model

     -> eligible
        -> assemble bounded, secret-free evidence
        -> advisory semantic model
           -> REJECT
              -> write decision receipt
              -> write not-merged outcome
              -> stop

           -> ESCALATE
              -> write decision receipt
              -> write not-merged outcome
              -> stop for human judgment

           -> APPROVE
              -> write decision receipt before mutation
              -> trusted postflight recollects all state
                 -> state changed or gate failed
                    -> write stale-decision outcome
                    -> stop

                 -> binding unchanged and all gates pass
                    -> exact-head merge request
                    -> write merged outcome receipt
```

## Deterministic preflight

The trusted pre-script obtains fresh GitHub state and must establish all of the
following before the model runs.

### Pull-request identity and state

- The repository is exactly the configured repository.
- The pull-request number comes from the trusted event URL.
- The pull request is open.
- The pull request is not a draft.
- The base branch is the configured branch, `main` in the lab.
- The pull request comes from the same repository, not a fork.
- GitHub native standing auto-merge is not enabled for the pull request.

### Revision and base binding

- The current head SHA is valid and recorded.
- The live base-branch SHA is fetched directly from the branch.
- The base SHA reported in the pull-request payload matches the live base SHA.
- GitHub's synthetic merge preview is available.
- The merge preview's ordered parents are exactly
  `[live_base_sha, head_sha]`.

The lab added the live-base and merge-preview checks after discovering that the
pull-request payload and merge preview could remain based on an older `main`
revision even while the user interface described the pull request as clean.

### Policy cohort

- The pull-request author is allow-listed.
- The change contains one to three files.
- Every changed path is allow-listed.
- The lab allows only `docs/example-feature.md` for the exercise.
- No deny label is present.
- Deny labels include `do-not-merge`, `hold`, `fullsend-no-merge`, and
  `security-review-required`.

### Checks

- Every required check exists.
- Every required check applies to the exact head SHA.
- Every required check completed.
- Every required check concluded successfully.
- Pending, failed, missing, cancelled, or timed-out required checks are
  ineligible.

The lab required:

- `Example contract`
- `Delayed integration (4 minutes)`

### Reviews and threads

- At least one approval applies to the exact head SHA.
- No latest reviewer state is `CHANGES_REQUESTED`.
- No review thread is unresolved.
- Review results are not truncated.

### Commits and DCO

- The commit list is present and complete for the supported cohort.
- Every pull-request commit includes a valid `Signed-off-by` trailer.

### Mergeability

- Mergeability is known.
- The pull request is mergeable.
- The mergeable state is `clean` or `unstable`. `unstable` is accepted only
  because the Auto-Merge check makes its own aggregate status non-passing while
  it runs; every policy-named required check is independently required to have
  succeeded for the exact head. `behind`, `dirty`, `blocked`, and unknown
  states remain ineligible.
- Conflicts and unknown states fail closed.

### Patch evidence

- Every changed file has an API-sourced patch.
- Each patch is bounded in size.
- The total patch evidence is bounded in size.
- Missing or oversized patch evidence is a deterministic failure.

The first Auto-Merge run revealed this requirement. The trusted checkout was at
the base revision, so the model could not inspect the pull-request patch. The
model correctly returned `ESCALATE` instead of guessing.

## Semantic assessment

The model receives a compact, secret-free evidence document containing:

- The immutable binding tuple.
- Pull-request title and bounded body.
- Author and change-size metadata.
- Deterministic findings.
- Required-check evidence.
- Approval evidence.
- Commit DCO evidence.
- Changed paths.
- Bounded API-sourced patches.
- The trusted policy.

The model evaluates only concerns not fully answerable by deterministic rules:

- Does the patch match the issue and pull-request description?
- Is the change routine and bounded?
- Is the documentation or implementation coherent and complete?
- Do the tests meaningfully cover the change?
- Is there hidden coupling or a security implication?
- Is the evidence ambiguous, suspicious, or insufficient?
- Does the change need a human decision?

### APPROVE

`APPROVE` means the exact bound revision is semantically eligible. An approval
must have no remaining risk signals.

### REJECT

`REJECT` means there is a concrete defect or policy mismatch. The controller
records the decision and does not merge.

### ESCALATE

`ESCALATE` means evidence is missing, ambiguous, suspicious, unusually risky,
or requires human judgment. Missing facts never count as approval.

## Trusted postflight

The model result is not sufficient authority. The trusted post-script:

1. Verifies the preflight evidence hash.
2. Verifies that the evidence policy exactly matches immutable runner policy.
3. Verifies that the model returned a valid structured result.
4. Verifies that the model copied the binding exactly.
5. Verifies that the event URL, repository, and pull-request number agree.
6. Writes the pending decision receipt.
7. Stops without mutation for `REJECT` or `ESCALATE`.
8. For `APPROVE`, recollects fresh state using the same trusted gate code.
9. Repeats all mutable deterministic checks.
10. Compares the fresh head/base binding with the approved binding.
11. Rejects any stale or newly ineligible state.
12. Calls the forge merge endpoint with the expected head SHA and squash method.
13. Writes the final outcome receipt.

The model sandbox never receives the merge credential.

## Why there are two receipts

The two comments can look repetitive, but they represent different events.

### Receipt 1: decision recorded

This receipt is written before mutation. It proves:

- Which exact tuple was evaluated.
- Which evidence hash was used.
- Which policy version applied.
- What the model decided.
- Why the model reached that decision.
- Which workflow run attempted the authority transition.
- When the decision was recorded.

It must continue to exist even if postflight rejects the decision as stale.

### Receipt 2: outcome recorded

This receipt is written after the attempt. It proves:

- Whether the pull request merged.
- Whether the decision was rejected as stale.
- Whether a non-approve decision produced no merge attempt.
- Which merge commit resulted when the merge succeeded.
- When the outcome was recorded.

### Recommended receipt refinement

Keep both append-only events. Reduce duplication by making the outcome receipt
reference the first receipt or evidence hash and include only:

- Outcome.
- Merge SHA, if any.
- Failure or stale reason, if any.
- Outcome timestamp.

Do not edit the write-ahead receipt after mutation. Mutating it would weaken the
audit trail.

## End-to-end lab exercise

### Isolation and safety gate

A new private repository, `ascerra/auto-merge`, was created for the exercise.
The user explicitly required that nothing affect the public Fullsend mint.

The lab used a dedicated workload-identity pool and provider with an exact
repository condition for `ascerra/auto-merge`. It added only the repository-
scoped inference principal needed by the lab. No public-mint deployment,
enrollment, update, disablement, deprovisioning, or deletion command was run.

Only the needed Fullsend GitHub role applications were installed for the new
repository. The repository was configured for squash merges, automatic branch
deletion, and no native standing auto-merge.

### Per-repository Fullsend installation

Fullsend was installed in per-repository mode from current source rather than
the older released binary. The lab configuration enabled:

- Triage.
- Coder.
- Review.
- Fix.
- The custom Auto-Merge harness.

The generated configuration initially omitted the Fix role. A real
`CHANGES_REQUESTED` event routed correctly but skipped Fix. The role was added
explicitly and a later Fix run succeeded.

### Issue-to-pull-request flow

Issue #1 requested a small documentation update. The exercise then performed:

1. `/fs-triage` on the issue.
2. Triage classification and routing.
3. Code-agent implementation.
4. Pull-request creation.
5. Review-agent assessment.
6. A requested semantic correction.
7. Fix-agent update.
8. Exact-head CI and approval verification.
9. Automatic review/CI readiness signals and `/fs-auto-merge` on the pull request.

The manual command remains an immediate evaluation path. The custom harness
also listens for an approved review and for the trusted
`fullsend-auto-merge-ready` label. The label is added only by the base-branch
readiness workflow after the exact CI workflow succeeds; it is a wake-up signal
and never replaces deterministic preflight.

### DCO discovery

The initial code-agent head did not contain the required `Signed-off-by`
trailer and was blocked. The Fix agent corrected the semantic wording but
declined to add DCO because of hosted policy. The equivalent final tree was
rewritten into a signed-off commit and rebased on the live base.

This is a lab workaround, not a production solution. Fullsend's autonomous
commit policy and repository DCO policy must be aligned.

### Deliberately slow CI

The workflow contained:

- A fast deterministic document validator.
- A second check that intentionally slept for 240 seconds and then ran the same
  validation.

The delayed check completed successfully in 4 minutes and 5 seconds. This
proved that an early Auto-Merge reconciliation must stop cheaply rather than
spend inference or leave standing merge authority while CI remains pending.

### Safe first Auto-Merge result

The first Auto-Merge run returned `ESCALATE`. The model lacked the actual
pull-request patch because the trusted checkout intentionally remained at the
base revision. The trusted post-script wrote the decision and not-merged
receipts. No merge occurred.

This failure was desirable: insufficient evidence failed closed.

### Hardened evidence contract

The implementation was changed to include bounded API-sourced patch evidence.
Missing or oversized patches became deterministic failures.

The implementation was also strengthened to fetch the live base SHA and verify
the synthetic merge preview's parent order. This addressed stale pull-request
base metadata observed during the lab.

### Successful result

The final run bound:

- Repository: `ascerra/auto-merge`
- Base branch: `main`
- Live base: `b76f1bb52a61b6a58a71131155007a3448406607`
- Exact head: `3b1a3ac102b9c4f2d40f9efb8ee6341a73ea6781`
- Merge preview: `8b629c4a8b31801de802d945ba2acf638ec1c311`
- Merge-preview parents: live base followed by exact head
- Evidence hash:
  `9863952b8f3aca8a3baa0bf65de4b2a4374de495b2cbed3b2820cd9e4801277d`

The semantic model returned `APPROVE`. Trusted postflight recollected state,
confirmed that the binding remained valid, and used an exact-head squash merge.

The resulting merge commit was:

```text
bfad1a03b207449dd0a139a22d37ddb6ead7b4f1
```

## Example cases

### Case 1: happy path

All deterministic gates pass. The model receives complete bounded evidence and
returns `APPROVE`. Postflight recollects identical state. The controller writes
the pending receipt, performs the exact-head merge, and writes the outcome
receipt.

Result: merge the exact head.

### Case 2: required CI is pending

The four-minute check is still running when an event triggers reconciliation.

Result: stop before model invocation. Spend no inference and attempt no merge.

### Case 3: a required check failed

A required check applies to the current head but concluded with failure.

Result: deterministic rejection before model invocation.

### Case 4: patch evidence is missing

The model cannot inspect the actual pull-request change.

Result: deterministic failure or semantic `ESCALATE`; do not merge.

### Case 5: patch evidence is oversized

The patch exceeds the configured per-file or total evidence bound.

Result: deterministic failure. Do not send unbounded content to the model.

### Case 6: an approval is stale

The latest approval applies to a previous head SHA.

Result: deterministic rejection. Require approval of the exact head.

### Case 7: changes are requested

A reviewer's latest meaningful state is `CHANGES_REQUESTED`.

Result: deterministic rejection. Continue the review/fix loop.

### Case 8: a review thread is unresolved

At least one review thread remains unresolved.

Result: deterministic rejection.

### Case 9: a commit lacks DCO

One pull-request commit lacks a valid `Signed-off-by` trailer.

Result: deterministic rejection before model invocation.

### Case 10: a hold label is present

The pull request contains `hold`, `do-not-merge`, or another configured deny
label.

Result: deterministic rejection.

### Case 11: a protected path changes

The pull request modifies a workflow, Fullsend configuration, agent prompt,
security contract, ownership file, or merge implementation.

Result: outside the low-risk cohort. Reject or require explicit human handling.

### Case 12: semantic intent mismatch

All forge checks are green, but the patch does not implement the issue or
contains a hidden risk.

Result: model returns `REJECT` or `ESCALATE`; trusted code does not merge.

### Case 13: the head changes after approval

A new commit is pushed after the semantic model approved the old head.

Result: fresh postflight binding differs. Record stale-decision rejection.

### Case 14: the live base changes after approval

Another pull request merges to `main` after the semantic decision.

Result: postflight rejects the stale base binding. Reconcile again against the
new base.

### Case 15: mergeability is unknown

GitHub has not finished calculating mergeability.

Result: fail closed and wait for a later event.

### Case 16: the forge response is ambiguous

The merge request may have succeeded, but the controller lost the response.

Result: inspect authoritative forge state and reconcile the receipt before any
retry. Never blindly retry a mutation with an unknown prior outcome.

### Case 17: the automatic readiness label reaches Fullsend but stale base configuration hides the agent

This was tested as a real hosted example on open PR #6 in the private
`ascerra/auto-merge` repository. The `fullsend-auto-merge-ready` label was
added after the earlier manual and review-driven examples.

- Fullsend run #99: https://github.com/ascerra/auto-merge/actions/runs/35344140609
- PR: https://github.com/ascerra/auto-merge/pull/6

The run was triggered by a real `labeled` pull-request event. Route completed
and Harness dispatch completed successfully in 1 minute 47 seconds. However,
the reusable workflow checked out the pull request event's stale `base.sha`
(`307b6f9`) instead of then-current `main` (`5975b78`). Auto-Merge did not
exist in that older configuration, so its matrix job was skipped. No
Auto-Merge decision comment was written, no post-script ran, and the PR was not
merged. The readiness label was removed after the test.

This is a useful negative result: the event reaches Fullsend, and the failure
is configuration checkout freshness rather than evidence of a CEL entity-shape
mismatch. Fresh PR #7 was created after the corrected configuration landed so
that the automatic path could be tested against the intended base. Production
still needs an explicit trusted-current-configuration policy for these
`pull_request_target` lifecycle events. The run also reported non-fatal cache
restore/write-scope warnings.

### Case 18: aggregate mergeability self-deadlocks on the controller's own check

The first fresh PR #7 attempt had exact-head CI success, a current approval,
resolved review threads, DCO sign-off, an allowlisted path, and no conflicts.
GitHub's UI reported the pull request ready to merge, but deterministic
preflight rejected `mergeable_state` because the Auto-Merge check itself was
still pending. GitHub describes `UNSTABLE` as mergeable with a non-passing
commit status; while the controller runs, its own status creates that condition.

The corrected policy accepts only `clean` or `unstable`. It remains safe because
the controller independently requires each policy-named check to be completed
with `success` on the exact head. `behind`, `dirty`, `blocked`, and unknown
states remain ineligible. Three new unit tests cover accepted `unstable` and
rejected `behind` and `blocked` states. The complete suite now has 41 passing
tests.

Result: avoid self-deadlock without weakening explicit exact-head CI,
conflict, base, review, DCO, scope, or postflight gates.

### Case 19: PR #7 automatically merges the exact approved head

PR #7 is the final hosted proof:

- PR: https://github.com/ascerra/auto-merge/pull/7
- Exact head: `ae9e2a0e00e7663791d92db191bc97085df4f293`
- Live base at authorization: `ba8a7e3bdd95749fb7e570bbe621c3adc6c7d827`
- CI run: https://github.com/ascerra/auto-merge/actions/runs/35770806123
- Review run: https://github.com/ascerra/auto-merge/actions/runs/35770804538
- Auto-Merge run #123: https://github.com/ascerra/auto-merge/actions/runs/35772620347
- Pending receipt: https://github.com/ascerra/auto-merge/pull/7#issuecomment-5782571165
- Merged receipt: https://github.com/ascerra/auto-merge/pull/7#issuecomment-5782573084
- Squash merge commit: `80449fd3b6fee6f35ae7b669765e54f917eabf3a`

The fast check and deliberate four-minute check passed. Fullsend Review then
approved the rebased exact head. That `pull_request_review` event automatically
started run #123 and selected only the custom Auto-Merge harness. Preflight
passed, the sandbox was read-only and had no `GH_TOKEN`, and the model returned
a schema-valid `APPROVE` result in one iteration. Trusted postflight wrote the
pending receipt, recollected all mutable facts, repeated the complete gate, and
called GitHub's expected-head squash merge endpoint. Nine seconds after the
pending receipt, GitHub accepted the exact-head merge and the controller wrote
the merged receipt.

The readiness label itself did not wake another workflow because GitHub
suppresses recursive workflow triggers caused by mutations made with the
workflow `GITHUB_TOKEN`. The approval event supplied the automatic wake-up in
this CI-first / review-second case. A production controller needs trusted
dispatch or periodic reconciliation so review-first / CI-second ordering is
also guaranteed.

## Why native "merge when ready" is insufficient by itself

Native forge auto-merge is useful. GitHub waits for configured required reviews
and status checks, and a merge queue can test a queued change against the latest
target branch and earlier queued changes.

The limitation is that the button delegates a future merge to whatever rules
are currently configured in the repository. It is not a complete authority
protocol.

### Problem 1: it is standing future authorization

The user enables auto-merge before readiness is complete, and the forge merges
later when its configured requirements become true. GitHub documents automatic
disablement when a contributor without write permission pushes to the head or
when the base branch changes. That is not the same guarantee as invalidating
authorization on every revision or evidence change.

### Problem 2: it checks only configured rules

If a check is missing, renamed, duplicated, incorrectly sourced, or not marked
as required, the native button does not know the organization intended a
stronger policy.

### Problem 3: review freshness controls are optional

Dismissal of stale approvals and approval of the most recent reviewable push
are separate branch-protection settings. A repository can require an approval
without proving that the approval applies to the exact head expected by this
design.

### Problem 4: latest-base testing is optional

A repository needs strict up-to-date status checks or a merge queue to test
against the latest target branch. Loose status checks allow a head that was
tested against an older base relationship.

### Problem 5: it does not perform semantic assessment

The native button does not decide whether the patch matches the issue, remains
routine and bounded, introduces hidden coupling, or requires human judgment.
Those checks must be implemented as an external required status or a trusted
controller decision.

### Problem 6: it does not produce the required authority receipts

The forge records ordinary audit events, but it does not create this design's
immutable evidence hash, semantic reasons, write-ahead decision receipt,
postflight tuple comparison, or explicit stale-decision outcome.

### Problem 7: bypass configuration can weaken protections

Branch protections and rulesets may allow administrators or designated actors
to bypass requirements unless the repository intentionally disables bypass.

### Problem 8: it does not solve controller idempotency

An external controller that loses a forge response still needs an idempotent
receipt and a fresh authoritative lookup before retrying. Clicking "merge when
ready" does not define that controller protocol.

### Recommended role for the forge

Use GitHub's exact-head merge API or merge queue as the final execution
mechanism behind the Fullsend authority boundary. Keep semantic assessment,
exact tuple binding, write-ahead receipt, and immediate postflight revalidation
in the trusted Auto-Merge controller.

Native auto-merge alone should not become a second Auto-Merge enablement path.

## Security and isolation findings

- The lab repository is private.
- The lab was the only repository placed in scope.
- Workload identity was scoped to exactly `ascerra/auto-merge`.
- The public Fullsend mint used separate resources and was not modified.
- No merge credential entered the model sandbox.
- The preflight evidence was secret-free and size-bounded.
- Tracked repository content and the final evidence were scanned for secret-like
  material.
- No credential was placed in commits, issue text, pull-request text, comments,
  or repository-captured logs.
- Native standing auto-merge remained disabled.
- The model could not alter trusted runner policy or the trusted event target.

## Validation performed

The latest implementation passed:

- 41 Auto-Merge and dispatch unit tests.
- Ruff linting.
- Python compilation.
- Bash syntax checks.
- ShellCheck.
- YAML parsing.
- JSON Schema parsing and result validation.
- Fullsend agent resolution.
- Whitespace validation.
- Tracked secret-pattern scanning.
- Local/remote branch freshness checks.
- Hosted repository-setting checks.

The unit-test cases included:

- Eligible snapshot.
- Stale approval.
- Pending check.
- Failed check.
- Hold label.
- Disallowed path.
- Missing patch.
- Oversized patch.
- Unknown mergeability.
- Stale reported base.
- Stale merge preview.
- Native auto-merge enabled.
- Unsigned commit.
- Unresolved review thread.
- Changes requested.
- Evidence-hash round trip.
- Bounded semantic patch presence.
- Valid structured model result.
- Stale model binding.
- `APPROVE` with a risk signal.
- Invalid decision enum.
- Receipt-before-merge ordering.
- Stale postflight binding without merge.
- Non-approve receipts without merge.
- Tampered repository binding.
- Tampered pull-request number.

## What the lab taught us

### Patch evidence must be explicit

A trusted base checkout does not contain the pull-request patch. The semantic
model needs bounded, authoritative change evidence.

### Pull-request base metadata can be stale

The controller must fetch the live base and verify the synthetic merge preview,
not trust only the base SHA embedded in the pull-request payload.

### DCO and autonomous commit policy must agree

The system should not need a human to rewrite bot history simply to satisfy a
known repository policy.

### The Fix role must be configured intentionally

A requested review/fix loop must ensure that Fix is actually enabled in the
per-repository role list.

### Two receipts are correct, but their presentation can improve

The write-ahead and outcome events must remain distinct. The second receipt can
be compact and reference the first.

### Aggregate mergeability must not include the controller as a hidden gate

Requiring only GitHub's aggregate `clean` state self-deadlocked while the
Auto-Merge check was pending. The controller now treats explicit required
checks on the exact head as authoritative and accepts `unstable` only when
those checks have succeeded. Conflict, behind, blocked, and unknown states
still fail closed.

### Readiness state and wake-up delivery are separate concerns

The readiness label correctly records that exact-head CI completed, but a
workflow-token label mutation does not recursively start Fullsend. Production
must provide trusted dispatch or periodic reconciliation rather than assume
the label event always fires.

### A successful lab is not production completion

The private experiment proved the core controller and exposed platform gaps.
It did not solve every production concern.

## Remaining production gaps

### Purpose-built merge identity

The hosted lab exposed the custom stage through the coder identity. Production
needs a dedicated least-privilege identity whose only privileged responsibility
is the authorized merge transition.

### Fullsend scaffold defaults

The generated per-repository role list omitted Fix. Fullsend should either
include it when a review/fix loop is requested or make the choice explicit.

### DCO policy alignment

Hosted code/fix policy and repository DCO requirements must agree so an
autonomous change can reach eligibility without manual history repair.

### Branch protection and rulesets

The private personal lab could not enable branch protection under the account's
plan. Production must use branch protection or rulesets in addition to the
trusted Auto-Merge controller.

### Atomic head and base authority

GitHub's merge API accepts an expected head SHA but does not provide an atomic
base-SHA compare-and-swap. Production needs a per-PR lease or merge-queue
authority so final base validation and mutation are serialized.

### Idempotent receipt store

GitHub comments were adequate durable receipts for the lab. Production needs an
idempotent receipt store and explicit forge-state reconciliation after
ambiguous timeouts.

### Reliable readiness wake-up

Add a trusted dispatch path or periodic reconciliation so both CI-first and
review-first event orderings eventually evaluate the current pull request.

### Trusted current configuration

Lifecycle events must load current trusted base-branch agent configuration,
while preserving the rule that untrusted pull-request head code is never used
as controller configuration.

### Receipt presentation

The current final receipt duplicates most of the write-ahead receipt. Preserve
both append-only events but make the outcome record concise.

## Suggested questions for NotebookLM

- Why must Auto-Merge bind both the head SHA and live base SHA?
- What is the difference between deterministic preflight and semantic review?
- Why is the model not allowed to hold the merge credential?
- Why did the first Auto-Merge run escalate?
- What did the lab discover about GitHub pull-request base metadata?
- Why are there two receipts?
- Which cases stop before model invocation?
- Which cases require the model to reject or escalate?
- What happens if the head changes after the Review Agent records its judgment?
- Why is native "merge when ready" insufficient by itself?
- How should a merge queue fit into the final production architecture?
- Which lab workarounds must not become production behavior?
- What remains before the Auto-Merge capability is production-ready?

## Glossary

**Auto-Merge agent**

The dedicated Fullsend agent that coordinates deterministic evidence, semantic
assessment, receipts, postflight, and exact-head mutation.

**Binding tuple**

The immutable repository, pull-request, head, base, policy, and evidence
identity to which a semantic decision applies.

**Compare-and-swap**

A mutation that succeeds only if the target still has the expected identity.
The lab supplied the expected head SHA to the GitHub merge endpoint.

**Deterministic gate**

A rule evaluated from authoritative forge state without model judgment.

**DCO**

Developer Certificate of Origin sign-off represented by a `Signed-off-by`
trailer in each commit.

**Evidence hash**

A SHA-256 hash over the canonical preflight evidence. It detects altered or
mismatched evidence.

**Exact head**

The specific 40-character Git commit SHA that was checked, reviewed, approved,
and authorized.

**Fail closed**

Treat missing, unknown, malformed, stale, or ambiguous state as ineligible.

**Forge**

The source-control hosting platform, GitHub in this lab.

**Live base SHA**

The current commit SHA fetched directly from the target base branch.

**Merge preview**

GitHub's synthetic merge commit representing the base and pull-request head.
The lab verifies the ordered parent tuple.

**Postflight**

The final trusted revalidation immediately before mutation.

**Preflight**

The trusted deterministic evidence collection and eligibility evaluation before
model invocation.

**Reconciliation controller**

An event-driven controller that repeatedly compares desired policy with current
state and acts only when the current state is eligible.

**Semantic decision**

The bounded model result: `APPROVE`, `REJECT`, or `ESCALATE`.

**Standing authority**

Permission granted now for a future merge when conditions later become true.
The Auto-Merge design avoids this model.

**Write-ahead receipt**

A durable record written before the privileged merge request.

## Evidence links

The following links are private and may require an authenticated GitHub
session. Their essential content is summarized in this document.

- Repository: https://github.com/ascerra/auto-merge
- Issue #1: https://github.com/ascerra/auto-merge/issues/1
- Pull request #2: https://github.com/ascerra/auto-merge/pull/2
- Triage run: https://github.com/ascerra/auto-merge/actions/runs/35169161822
- Code run: https://github.com/ascerra/auto-merge/actions/runs/35169615563
- Review run: https://github.com/ascerra/auto-merge/actions/runs/35170123039
- Fix-routing discovery:
  https://github.com/ascerra/auto-merge/actions/runs/35170672367
- Successful Fix run:
  https://github.com/ascerra/auto-merge/actions/runs/35171095208
- First safe Auto-Merge escalation:
  https://github.com/ascerra/auto-merge/actions/runs/35172951894
- Final CI run:
  https://github.com/ascerra/auto-merge/actions/runs/35214655514
- Final Review run:
  https://github.com/ascerra/auto-merge/actions/runs/35214653637
- Successful Auto-Merge run:
  https://github.com/ascerra/auto-merge/actions/runs/35216234955
- Pending decision receipt:
  https://github.com/ascerra/auto-merge/pull/2#issuecomment-5713721773
- Merged outcome receipt:
  https://github.com/ascerra/auto-merge/pull/2#issuecomment-5713723194

## External references

- GitHub, Automatically merging a pull request:
  https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request
- GitHub, About protected branches:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub, Managing a merge queue:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- Fullsend repository: https://github.com/fullsend-ai/fullsend
- Fullsend agents repository: https://github.com/fullsend-ai/agents

## Local companion documents

- `docs/IMPLEMENTATION-PLAN.md`
- `docs/AUTO-MERGE-SECURITY-CONTRACT.md`
- `docs/AUTO-MERGE-AGENT.md`
- `docs/auto-merge-lab-report-standard.html`
