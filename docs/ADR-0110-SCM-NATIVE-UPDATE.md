# Recommended ADR 0110 clarification

This document records what the SCM-native lab changes should teach the concise
ADR. It is implementation feedback, not a replacement ADR.

## The decision in one sentence

Add an opt-in Auto-Merge agent as a separate semantic authorization policy,
then let trusted Fullsend runtime code submit that exact authorization to the
repository's native direct or merge-queue path without recreating SCM policy.

## What the ADR should say explicitly

1. **SCM policy remains authoritative.** Fullsend does not require, infer,
   mirror, or replace branch protections. Enabling Auto-Merge does not cause
   Fullsend to invent a minimum SCM baseline.
2. **The Auto-Merge agent supplies a different policy.** It decides whether
   semantic evidence supports unattended merge: exact-head Review approval,
   assessed risk, relevant human context, optional Review quality evidence,
   and repository instructions.
3. **Trusted runtime binds and submits; the agent never mutates.** The runtime
   validates an exact revision/context binding and requests native auto-merge.
   GitHub still chooses whether to wait, queue, reject, or merge.
4. **Queue repositories use their queue.** A Fullsend authorization must not
   bypass or replace merge-queue policy. Queue-time Fullsend reauthorization is
   limited to ensuring that the semantic receipt remains valid for the
   queue-generated context.
5. **Review risk is an input, not an SCM replacement.** Repositories may set a
   maximum unattended-risk level. Auto-Merge consumes Review's assessment; it
   does not perform a second code review.
6. **Informal human context matters.** The agent may understand ordinary
   language such as a request to pause or coordinate even when the author did
   not file a formal blocking review. This is a clear example of value beyond
   SCM rulesets.
7. **Review quality is optional.** A repository may ignore, observe, or enforce
   trusted aggregate evaluation evidence such as `review_correctly_approved`.
   Repositories without that evaluation system remain supported.

## Wording to remove or avoid

- Claims that Fullsend verifies a minimum branch-protection baseline.
- Lists implying Auto-Merge checks CI, required reviews, conversation
  resolution, mergeability, or branch freshness itself.
- Language that treats generic native auto-merge as a competing mechanism.
  Native auto-merge is the SCM execution path after Fullsend authorization.
- A requirement that the first implementation use a post-script specifically.
  The durable decision is the trusted runtime authority boundary; a post-script
  is one implementation of it.

## Details that belong outside the ADR

Keep exact JSON schemas, comment markers, trigger CEL, quality-provider
adapters, receipt phases, correlation windows, and GitHub CLI commands in the
implementation contract. The ADR should define ownership and authority, not
freeze this POC's mechanics.
