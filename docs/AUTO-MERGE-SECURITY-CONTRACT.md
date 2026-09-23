# Auto-Merge security contract

Status: normative for this mutation-capable private lab; the Fullsend v1
contract remains authoritative for production

## Purpose

The Fullsend Review Agent is the semantic authority for whether a change is
acceptable. The Auto-Merge agent verifies that exact-head attestation, checks
fresh merge readiness, and invokes the repository's configured direct or queue
operation. In the private lab's `lab-automatic` mode only, that one revision
may be merged.

## Authority boundary

The model is advisory. It may return `APPROVE`, `REJECT`, or `ESCALATE`, but it
never receives the credential or network authority that performs a merge.
Only trusted postflight may mutate the pull request; `observe` never mutates.

An approval applies to one tuple:

```text
(repository, pull_request_number, head_sha, base_ref, base_sha, policy_fingerprint)
```

Changing any member invalidates the decision.

## State machine

```text
event -> deterministic merge-readiness preflight
      -> ineligible: record SKIP/REJECT and stop
      -> eligible: assemble bounded evidence including Review attestation
                  -> Auto-Merge verifies attestation and binding
                  -> authoritative postflight
                  -> durable pending receipt
                  -> final authoritative recheck
                     -> unchanged and eligible: merge exact head in lab mode
                     -> otherwise: reject stale decision and stop
```

The workflow is event-driven, but model invocation is readiness-driven. Early
events may cheaply reconcile and stop; they must not spend inference when CI,
reviews, or mergeability are still pending.

## Deterministic preflight

Before invoking Auto-Merge, the trusted pre-script must establish all of the following:

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
6. The trusted Fullsend Review Agent has approved the exact head SHA. An
   approval for an older revision is stale, and a human or other bot approval
   cannot substitute for this semantic attestation.
7. Mergeability is known and the pull request is not conflicted or behind under
   the repository's policy.
8. The repository's native standing auto-merge feature is not enabled for this
   pull request.

The pre-script emits a compact, secret-free evidence document and a canonical
hash over the bound state. It does not merge and does not enable auto-merge.

## Review attestation and execution decision

The Review Agent receives the change and decides whether it achieves its intent,
has acceptable scope and risk, and needs human judgment. Auto-Merge receives
only a bounded, trusted attestation of that decision. It must not perform a
second semantic review or infer missing facts.

- `APPROVE`: the Review Agent approved the exact revision and readiness is
  still valid.
- `REJECT`: the attestation or deterministic evidence is invalid.
- `ESCALATE`: the attestation is missing, stale, ambiguous, or requires a
  human decision.

The output must conform to the result schema and include the complete tuple,
context fingerprint, decision, concise reasons, and risk signals. Invalid or
incomplete output fails closed.

## Pending and outcome receipts

Observe mode writes a secret-free preview to the workflow log. Live lab mode
persists a pending PR comment after postflight and before the forge request,
including the tuple, policy/context fingerprints, workflow identity, and
idempotency key. It then records merged, rejected, aborted, reconciled, or
unknown outcome state.

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

## Lab mutation boundary

This POC accepts only `observe` and `lab-automatic`. Live lab mode uses GitHub's
expected-head merge API, squash only, after a second complete gate following the
pending receipt. Duplicate keys do not issue another request. An uncertain
response is reconciled against current PR state and is not retried. Production
must additionally implement the Fullsend v1 per-PR lease, persistent receipt
store, startup reconciliation, merge queue, and purpose-built forge driver.

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
