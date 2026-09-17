# Auto-Merge security contract

Status: normative for this lab

## Purpose

The Auto-Merge agent closes a pull request only after deterministic forge
state and a bounded semantic assessment agree that the exact current revision
is eligible. It is a reconciliation controller, not a standing permission to
merge future revisions.

## Authority boundary

The model is advisory. It may return `APPROVE`, `REJECT`, or `ESCALATE`, but it
never receives the credential or network authority that performs a merge.
Only the trusted post-script may mutate the pull request.

An approval applies to one tuple:

```text
(repository, pull_request_number, head_sha, base_ref, base_sha, policy_version)
```

Changing any member invalidates the decision.

## State machine

```text
event -> deterministic preflight
      -> ineligible: record SKIP/REJECT and stop
      -> eligible: assemble bounded evidence
                  -> model APPROVE/REJECT/ESCALATE
                  -> durable decision receipt
                  -> authoritative postflight
                     -> unchanged and eligible: merge exact head
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

The output must conform to the result schema and include the bound head SHA,
base SHA, evidence hash, decision, concise reasons, and risk signals. Invalid
or incomplete output fails closed.

## Write-ahead decision receipt

Before any merge attempt, the trusted runner writes a durable receipt containing
the bound tuple, deterministic findings, semantic decision, timestamps, and
the workflow/run identity. The receipt must exist even when postflight later
rejects the decision as stale. This makes every attempted authority transition
auditable.

## Authoritative postflight

Immediately before mutation, the post-script obtains fresh forge state and
repeats every mutable gate. It must verify at least:

- repository and pull request identity;
- exact head SHA, base ref, live base SHA, and merge-preview parent tuple;
- required check conclusions for that head;
- review decision and approval revision;
- draft/open state, labels, unresolved blockers, mergeability, and policy
  cohort;
- receipt integrity and an `APPROVE` semantic result.

Any mismatch, lookup error, unknown state, or race fails closed. The script
must never fall back to a less precise merge command.

## Merge mutation

The mutation must use the forge's compare-and-swap equivalent, supplying the
expected head SHA. If the forge reports that the head changed, the agent records
a stale-decision rejection and waits for a new reconciliation event. It does
not enable native auto-merge or leave behind standing authority.

## Human trigger

`/fs-auto-merge` follows the same preflight, semantic decision, receipt, and
postflight path. A human command requests evaluation; it does not bypass any
gate and is not itself an approval.

## Explicit non-goals

- Replacing branch protection or repository rulesets.
- Treating a forge approval as sufficient semantic evidence.
- Merging code from forks or untrusted cohorts in this initial lab.
- Auto-merging changes to workflows, Fullsend configuration, agent prompts,
  security policy, ownership files, or the merge implementation itself.
- Preserving or supporting the legacy `CODE_AUTO_MERGE` path.
