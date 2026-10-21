# Auto-Merge documentation map

**Current work: Fullsend + Gemara evidence evaluation and a bounded documentation
pilot.** Start with [current state and proof](attempts/02-policy-evaluation/CURRENT-STATE.md).
The older custom auto-merge model agent is disabled. General production readiness
remains hold; this repository is a public integration lab.

## Current guides

- [Current state and verified proof](attempts/02-policy-evaluation/CURRENT-STATE.md): the active architecture, exact hosted evidence, limits and next verification.
- [Shadow walkthrough](attempts/02-policy-evaluation/SHADOW-OBSERVATION.md): trace native Review evidence to a real Gemara hold.
- [Documentation auto-merge pilot](attempts/02-policy-evaluation/DOCUMENTATION-AUTO-MERGE-PILOT.md): narrow owner authorization, App-backed writer, queue checks, expiry and maintenance limits.
- [Implementation runbook](../gemara-auto-merge/README.md): files, pinned setup, supported Gemara semantics and tests.
- [Review evidence contract](attempts/02-policy-evaluation/REVIEW-EVIDENCE-CONTRACT.md): producer/consumer responsibilities, subject binding and trust boundaries.
- [Hosted vendored Review record](attempts/02-policy-evaluation/HOSTED-VENDORED-REVIEW.md): final native hosted proof plus chronological failed attempts.
- [Work log](attempts/02-policy-evaluation/WORKLOG.md): dated actions and evidence. Older entries describe their time, not current deployment.

## Versioned attempts and historical evidence

- [Attempt 1: agent-led authorization](attempts/01-agent-led/README.md): frozen baseline, preserved implementation paths and recorded exercises. It is inactive.
- [Attempt 2: Gemara evaluation](attempts/02-policy-evaluation/README.md): current experiment overview.
- [D1–D4 local validation snapshot](attempts/02-policy-evaluation/D1-D4-REPORT.md): October 16 pre-publication report. Later hosted proof is linked separately.
- [PR #41 proof identifiers](attempts/02-policy-evaluation/history/pr41-proof.json): historical protected merge using the earlier receipt route, not the new native publisher.
- [Evidence directory](evidence/): dated earlier lab exercises.
- [Historical reasoning](history/): architecture notes and earlier implementation records.
- [Recorded-demo material](demo/): narration/media for earlier exercises.

## Earlier agent-led contracts and visuals

These remain useful design and historical references. They are not the active
Gemara runtime guide; follow the current guides above for deployed behavior.

- [Auto-Merge agent implementation](AUTO-MERGE-AGENT.md).
- [Auto-Merge security contract](AUTO-MERGE-SECURITY-CONTRACT.md).
- [Requirements and constraints log](AUTO-MERGE-REQUIREMENTS-AND-CONSTRAINTS.md).
- [Earlier real-flow diagram](auto-merge-real-flow.html).
- [Earlier visual lab report](auto-merge-lab-report-standard.html).
- [NotebookLM research compendium](auto-merge-notebooklm-source.md): historical research, not the current operational entry point.

Their original paths are retained for existing links and citations. Use the
[immutable Attempt 1 baseline](attempts/01-agent-led/README.md) when citing its
implementation. Later safety constraints are documented in the current pilot and
contract; this cleanup does not weaken runtime protections.

## Future production proposals

- [Future implementation contract](AUTO-MERGE-FUTURE-CONTRACT.md).
- [Future implementation plan](AUTO-MERGE-FUTURE-IMPLEMENTATION-PLAN.md).
- [Architecture working note](history/FULLSEND-AUTO-MERGE-ARCHITECTURE-WORKING-NOTE.md).

These propose broader Fullsend responsibilities, provider/SCM interfaces and
production governance. They do not establish shipped features, accepted readiness
or an approved organizational auto-merge standard. Gemara, Fullsend and GitHub
have separate responsibilities; a successful evaluation does not grant merge
credentials or replace GitHub's protections.

- [Shared Review assessment](SHARED-REVIEW.md): manual retained replay and trust boundary.
