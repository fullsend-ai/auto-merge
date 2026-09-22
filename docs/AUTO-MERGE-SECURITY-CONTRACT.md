# Auto-Merge security contract

Status: normative for the observe-only POC; live-mode requirements are deferred
to the Fullsend v1 contract

## Purpose

The Auto-Merge agent evaluates whether deterministic forge state and a bounded
semantic assessment agree that the exact current revision would be eligible.
This POC is a reconciliation observer, not a standing permission to merge.

## Authority boundary

The model is advisory. It may return `APPROVE`, `REJECT`, or `ESCALATE`, but it
never receives the credential or network authority that performs a merge.
The observe-only post-script may not mutate the pull request.

An approval applies to one tuple:

```text
(repository, pull_request_number, head_sha, base_ref, base_sha, policy_fingerprint)
```

Changing any member invalidates the decision.

## State machine

```text
event -> deterministic preflight
      -> ineligible: record SKIP/REJECT and stop
      -> eligible: assemble bounded evidence
                  -> model APPROVE/REJECT/ESCALATE
                  -> decision preview in the workflow log
                  -> authoritative postflight
                     -> unchanged and eligible: record observe preview
                     -> otherwise: reject stale decision and stop
```

The workflow is event-driven, but model invocation is readiness-driven. Early
events may cheaply reconcile and stop; they must not spend inference when CI,
reviews, or mergeability are still pending.

## Deterministic preflight

Before inference, the trusted pre-script must establish all of the following:

1. The target is an open, non-draft pull request in the configured repository.
2. The current head SHA and base ref/SHA are recorded from fresh forge state.
   The base SHA comes from the live base branch, not only the pull-request
   payload. The payload's reported base SHA and the synthetic merge preview's
   ordered parents must match that live base SHA and exact head SHA.
3. The author and changed paths fit the configured low-risk cohort.
4. No hold label, changes-requested review, unresolved review blocker, or
   policy-denied path is present.
5. Required checks for the exact head SHA have completed successfully. Pending,
   skipped where required, neutral where disallowed, cancelled, timed-out, or
   missing checks are ineligible.
6. Required review approval applies to the exact head SHA. An approval for an
   older revision is stale.
7. Mergeability is known and the pull request is not conflicted or behind under
   the repository's policy.
8. The repository's native standing auto-merge feature is not enabled for this
   pull request.

The pre-script emits a compact, secret-free evidence document and a canonical
hash over the bound state. It does not merge and does not enable auto-merge.

## Semantic decision

The model receives only the bounded evidence needed to decide whether the
change is routine, internally consistent, adequately verified, and free of
signals that require human judgment. It must not infer missing facts.

- `APPROVE`: the exact revision is semantically eligible.
- `REJECT`: a concrete policy or quality defect makes it ineligible.
- `ESCALATE`: evidence is ambiguous, unusually risky, or requires a human
  decision.

The output must conform to the result schema and include the complete tuple,
context fingerprint, decision, concise reasons, and risk signals. Invalid or
incomplete output fails closed.

## Observe result record

The trusted runner writes a secret-free decision and outcome preview to the
workflow log. It does not comment on the PR. A durable write-ahead receipt is a
mandatory future requirement before any live mutation code is introduced.

## Authoritative postflight

After semantic evaluation, the post-script obtains fresh forge state and
repeats every mutable gate. It must verify at least:

- repository and pull request identity;
- exact head SHA, base ref, live base SHA, and merge-preview parent tuple;
- required check conclusions for that head;
- review decision and approval revision;
- draft/open state, labels, unresolved blockers, mergeability, and policy
  cohort;
- policy/context integrity and an `APPROVE` semantic result.

Any mismatch, lookup error, unknown state, or race fails closed. The script
must never fall back to a less precise merge command.

## Live mutation boundary

This POC accepts only `observe` mode and contains no merge mutation. Future live
mode must implement the Fullsend v1 lease, idempotency, durable pending receipt,
timeout reconciliation, merge-queue, current-policy, and expected-head
requirements before a constrained forge call can exist.

## Evaluation triggers

`/fs-auto-merge` follows the same preflight, semantic decision, receipt, and
postflight path. A human command requests immediate evaluation; it does not
bypass any gate and is not itself an approval.

The harness may also request evaluation when:

- a non-fork pull request receives an approved review; or
- the trusted `auto-merge-ready` workflow adds
  `fullsend-auto-merge-ready` after the exact required CI workflow succeeds.

These automatic events are wake-up signals, not eligibility evidence. The
pre-script must stop before model invocation when the other readiness condition
is missing, and it must recollect every mutable fact before any merge attempt.
The readiness label is removed when the PR receives new commits or closes, so
a later head cannot inherit an earlier CI wake-up signal.

## Explicit non-goals

- Replacing branch protection or repository rulesets.
- Treating a forge approval as sufficient semantic evidence.
- Merging code from forks or untrusted cohorts in this initial lab.
- Auto-merging changes to workflows, Fullsend configuration, agent prompts,
  security policy, ownership files, or the merge implementation itself.
- Preserving or supporting the legacy `CODE_AUTO_MERGE` path.
