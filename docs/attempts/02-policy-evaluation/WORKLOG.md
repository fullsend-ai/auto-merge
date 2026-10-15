# Trial change log

## Initial research

Explored synthetic evaluation, native SDK behavior, adapter substitution,
readiness, GitHub observation and vendored asset preparation. The complete
research was preserved locally before reducing this change for review.

## Reduced trial

Kept the native SDK assessment adapter, independent JSON reference, bounded
read-only GitHub observer, shared/repository test profiles and focused tests.
Removed the earlier evaluator, schema vendor tree, generated result bundles,
vendor probe, broad planning documents and walkthrough assets from the proposal.
Removed schema validation/Policy round-trip tests with their dependency tree;
the known compatibility limitation remains documented, not silently fixed.

Validation: 24 Python tests and 4 native Go tests pass; Python lint/format,
Go formatting and the repository's example-document validation pass.
CI now only builds the pinned SDK and runs the focused synthetic tests.
No GitHub/model/merge calls are part of that workflow.

Publication state: PR #27 remains a draft. Both legacy dispatch workflows were
manually paused before its initial publication. This reduction does not restore
dispatch, modify GitHub rules, publish a status, or activate merging.

## Real-PR trial setup

User authorized landing setup and iterating on main. Retained the existing rules
and merge queue. Added a trusted-main, read-only observer workflow with normalized
job summaries; scoped Fullsend roles to Review only. No PR checkout, workflow
logs, arbitrary commands, raw payload publication, merge or status writes are
part of the observer. Legacy custom-agent/context routes remain disabled.

Validation: 25 Python tests, 4 native Go tests, lint/format and example validation.
The new test checks that job summaries explain holds without retaining API text.

## Live trials and first correction

PR #27 landed through the existing merge queue. Observer setup was pushed to
main using a temporary admin bypass; the original ruleset was immediately
restored and read back. No controls were deleted. Fullsend Review dispatch was
restored only after verifying the review-only config and disabled custom agent.

Opened PR #28 (valid docs) and PR #29 (intentional invalid Status field). Manual
hosted observer runs completed successfully on both. During the initial pending-CI
observation, corrected the normalizer to report Unknown until checks finish,
while any completed unsuccessful check produces a failed CI predicate. Added
a regression test for pending, mixed failure/pending, mixed success/pending,
and all-success observations. These trials never request merging.
