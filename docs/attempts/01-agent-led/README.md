# Attempt 1: agent-led semantic authorization

Frozen reference: [`c06d5b8ba0f1be703ed83415986c179d97f3329c`](https://github.com/fullsend-ai/auto-merge/tree/c06d5b8ba0f1be703ed83415986c179d97f3329c).
This is an experiment baseline, not a production v1 release.

The custom Auto-Merge agent interprets bounded semantic context. Trusted host
code collects and revalidates evidence and requests the native SCM operation.
The model has no merge credential. GitHub owns repository protections and the
actual merge. These responsibilities remain useful when testing alternatives.

The baseline [documentation hub](https://github.com/fullsend-ai/auto-merge/blob/c06d5b8ba0f1be703ed83415986c179d97f3329c/docs/README.md)
separates current contracts, future design, historical evidence and recordings.
[baseline.json](baseline.json) records hashes of those documents. Their existing
paths are preserved; use the immutable commit links when citing Attempt 1.
Future contracts in that snapshot remain proposals, not demonstrated behavior.

The recorded lab exercises cover semantic evaluation, revision binding and a
single-PR native queue path. See the [evidence directory](https://github.com/fullsend-ai/auto-merge/tree/c06d5b8ba0f1be703ed83415986c179d97f3329c/docs/evidence)
for their stated boundaries. This spike does not rerun those exercises or claim
that their results generalize to production queues.

Attempt 2 keeps the custom agent, workflows, security contract and fixtures
unchanged. Its evaluator is a separate, non-mutating local experiment.
