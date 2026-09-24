# Auto-Merge requirements and constraints log

Status: living input to the Auto-Merge ADR and implementation review.

This document records the concrete use cases, boundaries, and limitations
identified while testing the public `fullsend-ai/auto-merge` lab. It is not a
second merge policy. GitHub remains authoritative for SCM policy and the final
merge operation.

## Core use cases

### 1. Fully autonomous Fullsend loop

An issue may be triaged, implemented, reviewed, evaluated by Auto-Merge, and
merged without a human watching the run. Auto-Merge must therefore consume a
trusted semantic review result, not require a person to click a merge button.

### 2. Multiple semantic review providers

Fullsend Review is one supported provider, not a mandatory dependency. A
repository may disable it and configure another provider such as Qodo. The
provider must supply a trusted, normalized attestation bound to the exact PR
head. An arbitrary comment is not an attestation.

The normalized attestation needs:

- provider identity;
- `APPROVE`, `REJECT`, or an equivalent explicit decision;
- exact reviewed head SHA;
- reviewer identity and run/review identity;
- timestamp;
- bounded summary or rationale; and
- a trusted adapter or artifact source.

Missing, stale, malformed, or mismatched provider evidence fails closed.

### 3. Merge-queue repositories

Auto-Merge must submit the exact reviewed head through the forge-native
auto-merge mechanism. If the repository requires a merge queue, the forge must
enqueue the PR and own queue admission, merge-group checks, and final merge.
Auto-Merge must not bypass or reimplement queue policy.

The lab must prove both paths:

1. direct native auto-merge when queue policy is absent; and
2. queue enrollment followed by merge-group validation when queue policy is
   required.

### 4. Human context outside formal review state

An ordinary trusted comment such as “hold until the release owner confirms” may
carry semantic coordination information that SCM cannot infer. Auto-Merge may
defer or escalate for that context. Formal review state, required checks,
conversation resolution, branch freshness, mergeability, and queue state remain
SCM responsibilities.

### 5. Optional quality evidence

Review-quality measurements such as `review_correctly_approved` may be used as
repository policy in `off`, `observe`, or `enforce` mode. The feature must be
optional because not every Fullsend installation runs an LLM judge. Quality
evidence must be authenticated, scoped to a reviewer/version/time window, and
must never be placed in the sandbox with credentials.

## Constraints

- The model has no forge credential and cannot merge, comment, label, or change
  policy.
- The trusted host must bind every authorization to repository, PR number, head
  SHA, base ref/SHA, policy fingerprint, semantic fingerprint, and context
  fingerprint.
- The semantic stage must not become a second code reviewer. The configured
  review provider owns correctness, security, and issue-intent judgment.
- Auto-Merge validates that the provider result is legible, coherent, current,
  and safe to use as authorization; it may escalate when the result appears
  contradictory or hallucinated.
- SCM policy is not duplicated: Auto-Merge does not evaluate required checks,
  approval counts, conversation resolution, branch freshness, mergeability, or
  queue mechanics.
- A provider adapter must be trusted host code or a trusted artifact producer;
  raw user-authored text cannot grant merge authority by itself.
- Queue-generated revisions and multi-PR merge groups remain a production
  integration concern. The POC must at least prove a single-PR queue path and
  record what happens.
- No secret, access token, raw transcript, or private infrastructure identifier
  may be written to the evidence file, public report, or repository history.

## Test matrix

| Case | Expected result |
| --- | --- |
| Fullsend Review approves exact head | Auto-Merge may authorize after semantic validation. |
| Fullsend Review disabled with no replacement | Auto-Merge skips and does not request a merge. |
| Qodo/third-party adapter approves exact head | Auto-Merge may authorize using the normalized attestation. |
| Third-party comment without trusted adapter | Auto-Merge skips; comment is not authority. |
| Review evidence is stale or for another head | Auto-Merge skips. |
| Human hold or coordination request | Auto-Merge defers or escalates. |
| Direct SCM path | GitHub performs the native merge after authorization. |
| Required merge queue | GitHub enrolls the PR and controls merge-group checks and final merge. |
| Required SCM policy fails | GitHub waits or rejects; Auto-Merge does not bypass it. |

## Open ADR questions

1. Which providers will Fullsend ship adapters for initially?
2. What exact signed or authenticated attestation format will production use?
3. How will a provider result be reauthorized for a queue-generated merge group?
4. Which review-quality metrics, if any, belong in repository policy defaults?
5. What durable lease and receipt store will make retries idempotent across
   runner crashes?
