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
