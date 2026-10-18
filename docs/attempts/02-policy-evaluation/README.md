# Attempt 2: Fullsend + native Gemara evaluation

**Active experiment. Start with [current state and hosted proof](CURRENT-STATE.md).**
The previous custom auto-merge model agent is disabled. This public lab uses
native Gemara catalogs/policies, trusted Fullsend evidence and a separately
authorized GitHub queue writer. Production readiness remains **hold**.

## What was demonstrated

- [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41): automatic App-backed
  protected merge using the earlier verified receipt route.
- [PR #43](https://github.com/fullsend-ai/auto-merge/pull/43): real hosted vendored
  Fullsend native publication and independent automatic Gemara consumption.
  Its approval still held on an open finding and unestablished change class.

These are separate proofs. A successful merge through the newest native-artifact
route has not yet been demonstrated. The owner-enabled documentation pilot does
not qualify the repository for general production autonomy.

## Reading order

1. [Current state](CURRENT-STATE.md): exact evidence, scope, expiry and limits.
2. [Shadow walkthrough](SHADOW-OBSERVATION.md): a real native evaluation.
3. [Pilot runbook](DOCUMENTATION-AUTO-MERGE-PILOT.md): authorization, writer and queue.
4. [Implementation](../../../gemara-auto-merge/README.md): policies, supported semantics and local commands.
5. [Review contract](REVIEW-EVIDENCE-CONTRACT.md) and [hosted record](HOSTED-VENDORED-REVIEW.md): trust and publication details.

## Historical records

[D1–D4](D1-D4-REPORT.md) preserves the October 16 pre-publication local validation.
[The work log](WORKLOG.md) records subsequent changes chronologically. Earlier
claims about synthetic-only publication, uncommitted binaries or pending hosted
proof describe those earlier stages; they are superseded by the current-state page.
Schema v1.5.0 and the separately pinned Go SDK are described in the implementation
runbook. Unsupported policy semantics hold explicitly. This is a bounded Gemara
integration, not all governance layers or an approved organizational standard.
