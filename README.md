# Auto-Merge Agent Lab

Private integration lab for designing and exercising Fullsend's Auto-Merge
agent. The lab proves the complete path from an issue through triage, coding,
review/fix, CI, semantic eligibility evaluation, and an exact-head merge.

The merge agent is intentionally conservative. It may merge only when both
layers agree:

1. deterministic policy checks establish that the pull request is currently
   eligible; and
2. a model evaluates the bounded evidence and returns `APPROVE`.

The post-script then repeats every mutable check against the current pull
request head before it performs the merge. A stale decision can never merge a
newer commit.

See [the security contract](docs/AUTO-MERGE-SECURITY-CONTRACT.md) and the
[living implementation plan](docs/IMPLEMENTATION-PLAN.md).

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
- Do not enable GitHub's standing auto-merge facility for the exercise.
- The Auto-Merge agent can be requested immediately with `/fs-auto-merge`, or
  it can wake automatically after an approved review and after the trusted CI
  readiness workflow adds `fullsend-auto-merge-ready`. These are only
  evaluation signals; deterministic preflight remains authoritative.
