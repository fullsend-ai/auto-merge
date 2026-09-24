# Auto-Merge Agent Lab

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

See [the security contract](docs/AUTO-MERGE-SECURITY-CONTRACT.md) and the
[living implementation plan](docs/IMPLEMENTATION-PLAN.md).

The detailed design intentionally removed from
[Fullsend ADR 0110](https://github.com/fullsend-ai/fullsend/blob/main/docs/ADRs/0110-dedicated-auto-merge-authority-boundary.md)
is preserved here for follow-up implementation work:

- [future implementation contract](docs/AUTO-MERGE-FUTURE-CONTRACT.md)
- [future implementation plan](docs/AUTO-MERGE-FUTURE-IMPLEMENTATION-PLAN.md)
- [architecture working note](docs/FULLSEND-AUTO-MERGE-ARCHITECTURE-WORKING-NOTE.md)

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
