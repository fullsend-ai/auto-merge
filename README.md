# Auto-Merge Experiments Lab

## Attempts and current work

- [Attempt 1: agent-led authorization](docs/attempts/01-agent-led/README.md)
  preserves the installed lab at an immutable baseline commit. Existing
  contracts, evidence and recordings retain their paths.
- [Attempt 2: policy evaluation](docs/attempts/02-policy-evaluation/README.md)
  includes a fixture demo and [platform experiments](experiments/autonomy-platform/README.md)
  for readiness, four modes, SDK reuse and an independent adapter. Read-only
  GitHub observations and native vendor-content preparation are retained.
  No experiment authorizes a merge or invokes the installed agent.

The local setup disables the legacy agent registration and supplementary route,
preserves its scripts, and adds an unprivileged fixture CI definition. Main
adoption requires human review; fixture CI does not enable live merging. Read
[Attempt 2's safety boundary](experiments/gemara-spike/SECURITY.md) before running
or publishing it. The existing lab description below applies to Attempt 1.

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
[Fullsend ADR proposal (PR #7151)](https://github.com/fullsend-ai/fullsend/pull/7151)
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
