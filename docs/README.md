# Auto-Merge documentation hub

This is the starting point for understanding the Auto-Merge lab, the current
architecture, the evidence it produced, and the work that remains before a
production Fullsend offering.

Repository snapshot: `fullsend-ai/auto-merge` `main` at `4293fb8` (`test:
exercise fast review path (#26)`). The repository is a lab and reference
implementation. It is not a production-ready cross-SCM merge service.

## The decision in one paragraph

Auto-Merge is an opt-in semantic authorization stage around the repository's
existing SCM merge policy. The configured review provider—Fullsend Review by
default, or a trusted third-party adapter—owns the code-review judgment. The
Auto-Merge stage checks whether that provider's exact-head result is legible,
current, coherent with bounded intent/risk/context evidence, and suitable for
unattended authorization. Trusted host code binds the result to an exact
revision, revalidates mutable state, and asks the SCM to use its configured
direct or merge-queue path. The model has no merge credential and never
reimplements SCM policy.

## Start here

Read these in order:

1. [Auto-Merge agent](AUTO-MERGE-AGENT.md) — the current lab runtime contract.
2. [Security contract](AUTO-MERGE-SECURITY-CONTRACT.md) — trust zones,
   credentials, evidence binding, fail-closed behavior, and SCM handoff.
3. [Requirements and constraints](AUTO-MERGE-REQUIREMENTS-AND-CONSTRAINTS.md)
   — the living record of use cases, provider neutrality, queue behavior,
   human context, optional quality evidence, and open questions.
4. [Real flow](auto-merge-real-flow.html) — visual walkthrough of the current
   host, sandbox, post-script, and SCM path.
5. [Standard lab report](auto-merge-lab-report-standard.html) — the broadest
   visual and evidence-oriented report.

For a short explanation, start with the repository [README](../README.md).

## Current model

### What the SCM owns

The SCM remains authoritative for required checks, formal reviews, CODEOWNERS,
conversation resolution, branch freshness, mergeability, protected paths,
merge methods, queue admission, merge-group checks, and final merge.

### What the review provider owns

The configured review provider evaluates correctness, security, and whether the
change fulfills its intended outcome. Its result must be normalized into a
trusted exact-head attestation. A normal comment, arbitrary label, or ordinary
SCM approval is not automatically a semantic attestation.

### What Auto-Merge owns

Auto-Merge composes the provider attestation with bounded intent, changed-file,
risk, human-context, and optional quality evidence. It asks whether the result
is trustworthy enough for unattended authorization. It may authorize, defer,
or escalate; it does not perform the provider's code review again.

### What the trusted runtime owns

The trusted pre-script collects bounded evidence and avoids an expensive model
run when the candidate is already ineligible. The sandboxed agent has no forge
credential. The trusted post-script validates the structured result, records a
pending receipt, recollects mutable state, and submits the exact head through
the SCM's configured path. “Preflight” and “postflight” describe phases; the
implementation hooks are the pre-script and post-script.

### What is proven versus still future work

- Proven in the lab: issue-to-PR flow, review/fix loop, deterministic
  eligibility gates, bounded semantic evidence, exact-head binding, trusted
  post-script revalidation, direct native merge, and a single-PR merge-queue
  path with merge-group checks.
- Not production-complete: a durable cross-run receipt/lease service, robust
  multi-PR queue reauthorization, portable SCM adapters, supported provider
  attestation storage, production identity/permission design, and a complete
  AISDLC-29 verification/MVE contract.
- Important boundary: the lab's queue proof demonstrates SCM queue enrollment
  and queue-time checks. It does not make the current POC a general solution
  for reauthorizing every semantic decision against every future synthetic
  merge-group revision.

## Relationship to AISDLC-29

AISDLC-29 is broader than improving the Review Agent. It defines the concepts
that a central ADLC platform may eventually standardize: change impact, risk
tiers, minimal viable evidence, verification debt, relevant test selection,
evidence freshness, and remediation outcomes.

Fullsend should provide the portable evidence and attestation contracts,
provider/SCM adapters, secure orchestration, auditability, and recommended
profiles. Individual repositories should provide their own tests, CI, risk
appetite, CODEOWNERS, protected paths, human gates, and mapping from local
checks to the shared evidence vocabulary. Fullsend should not force every
repository to use identical CI job names or identical SCM rules.

The detailed future design is in [Auto-Merge Future Contract](AUTO-MERGE-FUTURE-CONTRACT.md).
It is a target contract, not a description of everything currently implemented.

## Document map

### Current contracts and decisions

- [AUTO-MERGE-AGENT.md](AUTO-MERGE-AGENT.md) — current agent behavior and
  implementation contract.
- [AUTO-MERGE-SECURITY-CONTRACT.md](AUTO-MERGE-SECURITY-CONTRACT.md) — current
  public-lab security boundary.
- [AUTO-MERGE-REQUIREMENTS-AND-CONSTRAINTS.md](AUTO-MERGE-REQUIREMENTS-AND-CONSTRAINTS.md)
  — living requirements, constraints, test matrix, and unresolved ADR questions.
- [auto-merge-real-flow.html](auto-merge-real-flow.html) — current visual flow.
- [auto-merge-lab-report-standard.html](auto-merge-lab-report-standard.html) —
  detailed visual lab report.

### Future production design

- [AUTO-MERGE-FUTURE-CONTRACT.md](AUTO-MERGE-FUTURE-CONTRACT.md) — desired
  cross-repository authority, data, queue, lease, receipt, and provider contract.
- [AUTO-MERGE-FUTURE-IMPLEMENTATION-PLAN.md](AUTO-MERGE-FUTURE-IMPLEMENTATION-PLAN.md)
  — phased production implementation plan.

These documents must be read with their status labels. They describe intended
production behavior and known gaps; they do not prove that the lab already
implements every future requirement.

### Lab evidence and examples

- [auto-merge-notebooklm-source.md](auto-merge-notebooklm-source.md) — a large
  research and evidence compendium, useful for deep dives but not the primary
  architecture contract.
- [auto-merge-queue-proof-2026-09-23.html](evidence/auto-merge-queue-proof-2026-09-23.html)
  — dated merge-queue exercise.
- [merge-queue-proof.md](evidence/merge-queue-proof.md) — short queue proof pointer.
- [queue-human-context-proof.md](evidence/queue-human-context-proof.md) — dated human
  context and queue scenario.
- [linked-issue-evidence-smoke.md](evidence/linked-issue-evidence-smoke.md) — linked
  issue context exercise.
- [structured-output-receipt-proof.md](evidence/structured-output-receipt-proof.md) —
  structured result and receipt exercise.
- [auto-merge-agent-smoke.md](evidence/auto-merge-agent-smoke.md) — smoke-test pointer.
- [example-feature.md](example-feature.md) — test fixture used by the lab.

### Historical reasoning and implementation records

- [ADR-0110-SCM-NATIVE-UPDATE.md](history/ADR-0110-SCM-NATIVE-UPDATE.md) — feedback
  captured while refining the Fullsend ADR; not the ADR itself.
- [FULLSEND-AUTO-MERGE-ARCHITECTURE-WORKING-NOTE.md](history/FULLSEND-AUTO-MERGE-ARCHITECTURE-WORKING-NOTE.md)
  — exploratory architecture reasoning.
- [IMPLEMENTATION-PLAN.md](history/IMPLEMENTATION-PLAN.md) — original lab build and
  validation record.
- [auto-merge-lab-demo-script.md](demo/auto-merge-lab-demo-script.md) — narration
  for the recorded demo.

These are valuable history, but a reader should not treat them as the current
normative contract when they conflict with the current agent, security, or
requirements documents.

### Presentation assets

The remaining HTML reports and `demo/` files are visualizations,
screenshots, audio, video, captions, and build helpers. They are evidence and
presentation material, not architecture authority.

## Cleanup disposition

The documentation directory currently mixes contracts, future plans, historical
notes, dated proofs, and media. The safe cleanup sequence is:

1. Keep this hub and make it the only required entry point.
2. Keep the three current contract documents and the two primary visual reports
   easy to find.
3. Move historical reasoning, dated proof pages, and demo narration into
   clearly named `docs/history/`, `docs/evidence/`, and `docs/demo/` folders.
4. Preserve the files and update relative links rather than deleting the lab
   record.
5. Regenerate or archive `history/auto-merge-current-flow.html`; its embedded links are
   pinned to an older commit and should not be presented as the current flow.
6. Remove duplicate or empty proof pointers only after confirming that no
   workflow, README, or external link depends on them.
7. Keep large media only when it is intentionally part of the public lab
   record; otherwise publish a release artifact or retain it outside the source
   documentation tree.

This disposition is intentionally conservative: the first cleanup should improve
navigation and status labeling without destroying evidence or silently changing
the runtime.
