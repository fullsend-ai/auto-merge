# Proposed amendment to ADR 0110

Status: proposal for review, not an applied upstream decision.

Reference: [open PR #7151](https://github.com/fullsend-ai/fullsend/pull/7151),
head [`84070f941acd6abd8d2b1c0ea663dbd550a2612a`](https://github.com/fullsend-ai/fullsend/blob/84070f941acd6abd8d2b1c0ea663dbd550a2612a/docs/ADRs/0110-dedicated-auto-merge-authority-boundary.md).
The spike provides synthetic evaluation evidence, not a deployment proof.

## Preserve

Keep a dedicated opt-in stage, a trusted semantic provider, exact-revision
binding, host credential isolation, final revalidation, native SCM execution,
no administrator bypass, and durable authorization/outcome records. Preserve
the stated migration away from competing Code-agent merge paths.

## Suggested replacement for the stage implementation decision

> Fullsend provides a dedicated Auto-Merge stage that consumes a configured
> trusted semantic provider's revision-bound result, repository-defined
> unattended scope, and required evidence. A deterministic gate consumes the
> configured policy adapter's evidence-backed result. The adapter may use
> Gemara-compatible controls and evaluation or another organization-selected
> policy engine. Semantic judgments originate in Review or specialized
> verification. Neither the evaluator nor an optional diagnostic model receives
> merge credentials or overrides a failed required condition. Unknown or
> unsupported required evidence holds or escalates the candidate.
>
> Trusted runtime code binds the recommendation to the current candidate and
> trusted policy, refreshes authoritative state, and requests only the
> repository's permitted native direct or queue operation. The SCM enforces
> mechanical policy and performs the merge. Gemara-compatible artifacts may
> represent controls, policy and evaluation records; they do not supply merge
> authority or make a specific implementation mandatory.

## Evidence and limits behind the change

Attempt 2 demonstrates schema-valid controls and policy, conservative evaluation
of structured synthetic evidence, traceable results, and equivalence to the
same rules expressed as plain JSON. A second model is unnecessary for those
cases. This does not prove that every human instruction or ambiguous semantic
context can be handled deterministically. Such capabilities need separately
evaluated upstream Review/verifier support. The current Python evaluator is
experiment scaffolding; Gemara SDK/evaluator reuse and an alternative engine
must be tested before selecting the platform implementation.

An optional shadow observer can measure additional hold recommendations without
credentials or live actions. If it supplies value, place that capability where
the evidence contract can represent it. The spike did not run that experiment.

## Decisions still needed

- Which semantic eligibility capability, if any, remains after upstream Review?
- Which evidence requirements are non-waivable minima versus repository choices?
- How is semantic evidence reauthorized for queue-generated revisions?
- How do authenticated evaluation records connect to a durable merge receipt?
- How do repository qualification and its revocation use the same policy adapter?
- How are shared mandatory controls and trusted repository policy composed?

The [platform experiment plan](SPIKE-PLAN.md) treats engine selection as separate
from Off, Shadow, Light and policy-governed behavior. These settings are proposed,
not an already shipped Fullsend configuration contract.

Use the runnable evidence and findings to review these choices before changing
the upstream ADR. If an accepted decision is later superseded, record that
explicitly rather than rewriting historical evidence.
