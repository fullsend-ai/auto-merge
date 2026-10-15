# Auto-Merge Experiments Lab

## Current experiment: native Gemara policy and a repeatable pilot draft

[Attempt 2](experiments/autonomy-platform/README.md) evaluates native Gemara
catalogs and imported common/repository policies against readiness and real PR
evidence. Input artifacts and generated EvaluationLogs are schema-validated.
Start with the [shadow walkthrough](docs/attempts/02-policy-evaluation/LIVE-TRIAL.md)
or the [live trial and its limits](docs/attempts/02-policy-evaluation/LIVE-PILOT.md).

**Current status:** the repeatable implementation is a draft on PR #32, not installed
on main. The earlier one-PR live merge is historical evidence.

The [repeatable pilot](docs/attempts/02-policy-evaluation/LIVE-PILOT.md) introduces
a time-boxed owner-enabled documentation cohort. The experimental maintenance
path remains disabled and excludes governance changes. The draft writer uses a dedicated temporary repository App; registration,
installation and hosted proof are tracked separately. Fullsend-native token
minting remains unresolved; no unmerged upstream workflow or personal token is used. Read the
trial record for the actual hosted proof and limits. Main requires the Gemara queue
gate and ordinary CI. Production readiness remains a separate qualification.

[Attempt 1](docs/attempts/01-agent-led/README.md) preserves the earlier agent-led
approach at its original paths. That agent and its supplementary dispatch route
remain disabled. Official Fullsend Review is active, with the documented pinned
host risk-receipt extension. The read-only verifier exercises positive PR #28,
negative PR #29 and the independent repository-readiness hold.

The existing lab description below documents Attempt 1.

Integration lab for designing and exercising Fullsend's Auto-Merge agent. The
recorded exercises were run while the repository was private and prove the complete path from an issue through triage, coding,
review/fix, CI, semantic eligibility evaluation, and an exact-head merge.

The current experiment deliberately does **not** reproduce GitHub's merge
policy. GitHub remains the only authority for required CI, required reviews,
conversation resolution, branch freshness, mergeability, and merge-queue
execution. Fullsend adds one separate policy: whether the current semantic
context permits unattended merge.

The Auto-Merge agent consumes the Review Agent's exact-head approval, its risk
assessment, ordinary human conversation, optional Review quality evidence, and
repository-specific instructions. Trusted host code binds that decision to the
exact revision and semantic context, then asks GitHub to use native auto-merge.
GitHub may wait, queue, reject, or merge according to its own rules.

Start with the [documentation hub](docs/README.md). It distinguishes current
contracts, future production design, historical lab evidence, and presentation
assets. The [security contract](docs/AUTO-MERGE-SECURITY-CONTRACT.md) and
[living requirements](docs/AUTO-MERGE-REQUIREMENTS-AND-CONSTRAINTS.md) are the
next documents to read.

The detailed design intentionally removed from
[Fullsend ADR 0110](https://github.com/fullsend-ai/fullsend/blob/main/docs/ADRs/0110-dedicated-auto-merge-authority-boundary.md)
is preserved here for follow-up implementation work:

- [future implementation contract](docs/AUTO-MERGE-FUTURE-CONTRACT.md)
- [future implementation plan](docs/AUTO-MERGE-FUTURE-IMPLEMENTATION-PLAN.md)
- [architecture working note](docs/history/FULLSEND-AUTO-MERGE-ARCHITECTURE-WORKING-NOTE.md)

## Exercise fixture

The end-to-end exercise asks Fullsend to update `docs/example-feature.md`. CI
validates that document immediately and again after a deliberate four-minute
delay, providing both fast and slow required checks for the merge agent.

Run the validator locally with:

```bash
python3 scripts/validate_example.py
```

## Safety

- Never commit credentials or local environment files.
- The Auto-Merge agent can be requested immediately with `/fs-auto-merge`, or
  wake after the Review Agent approves or a trusted human changes relevant PR
  conversation. Those events only request semantic reevaluation.
- The trusted pre-script skips model invocation when required semantic inputs
  are missing, stale, or outside configured unattended-risk and quality limits.
- GitHub native auto-merge and the merge queue remain authoritative after
  Fullsend submits its exact-head authorization.
