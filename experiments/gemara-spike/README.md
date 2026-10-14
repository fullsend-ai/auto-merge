# Attempt 2: local Gemara policy-evaluation spike

This experiment implements **policy → synthetic evidence → evaluation →
recommendation**. It does not merge, call an LLM, query a forge, or invoke the
installed custom agent. `eligible_for_demo_only` is not merge authorization.
The original workflow and agent remain Attempt 1.

Next-phase scope: [platform integration experiments](../../docs/attempts/02-policy-evaluation/SPIKE-PLAN.md)
cover repository qualification, four modes, centrally managed and repo policies,
Gemara SDK reuse, an alternative engine and secure vendored testing. These are
planned experiments, not features implemented by the fixture runner.

## Run it

Use Python 3.11 or newer. The evaluator and tests use the Python standard
library. Official schema validation also needs the pinned CUE binary. The
bootstrap currently supports Linux x86-64 and downloads one official release
archive, verifies its digest, and installs into ignored `.tools/`.

From the repository root:

```sh
python3 experiments/gemara-spike/bootstrap_cue.py
python3 experiments/gemara-spike/validate.py
python3 -m unittest discover -s experiments/gemara-spike -p test_spike.py
python3 experiments/gemara-spike/demo.py
```

Only bootstrap requires network access. CUE validates the vendored, hash-pinned
schemas offline. CUE receives a small clean environment, without inherited
credentials. Nothing here needs a GitHub token or model credential.

Run one scenario into a new directory inside ignored `out/`:

```sh
python3 experiments/gemara-spike/run.py \
  --evidence experiments/gemara-spike/fixtures/stale-review.json \
  --policy baseline \
  --output experiments/gemara-spike/out/my-stale-review
```

The same rules can emit plain JSON without executing CUE:

```sh
python3 experiments/gemara-spike/plain_baseline.py \
  --evidence experiments/gemara-spike/fixtures/satisfied.json --policy baseline
```

This baseline is a representation comparison using the same evaluator, not an
independent correctness oracle or a competing policy language implementation.

## Recorded walkthrough

Open [walkthrough.html](walkthrough.html) to step through actual local output,
read [walkthrough.txt](walkthrough.txt), or replay [walkthrough.cast](walkthrough.cast)
with an asciicast-compatible player. The recording contains only controlled
synthetic demo output; it is not a captured shell session or environment dump.
The HTML works offline and has no external script or network dependency.

## What each component does

- `catalog.json`: an actual Gemara ControlCatalog with CI, independent review,
  and an optional repository-specific scan requirement.
- `policies/`: actual Gemara Policy artifacts. Baseline excludes the extra
  repository control; the repository profile includes it.
- `engine.resolve_policy`: custom import/exclusion resolution, assessment-plan
  mapping, and a demo minimum floor. Gemara does not supply this engine.
- `engine.evaluate`: custom deterministic checks on revision identity,
  logical freshness, synthetic trust, independence and outcomes.
- `engine.gemara_log`: maps assessed results into a Gemara EvaluationLog.
- `validate.py`: uses official CUE schemas for structural validation. It does
  not authenticate evidence, evaluate policy, sign results or authorize actions.
- `adapters.py`: two representative synthetic review-provider mappings.
  These are examples of the adapter boundary, not live provider integrations.
- `run.py`: retains the input, effective policy, evaluation, recommendation,
  comparison, source digests and a short human-readable report.

Every input and output is marked synthetic. `synthetic-trusted` is an explicit
fixture assumption, not a production verification mechanism. Input timestamps
are assessed against the fixture's `evaluation_time`, so scenarios remain
repeatable. Assessment start/end timestamps describe the actual local run.

## Walkthrough

`demo.py` runs 13 evaluations:

1. All baseline requirements satisfied: `eligible_for_demo_only`.
2. CI failed: `hold`.
3. Review missing: `hold`.
4. Review bound to an older candidate: `hold`.
5. Extra repository scan failed, baseline policy: the extra control is not required.
6. The same evidence, repository policy: `hold` because the extra control is required.
7. Extra repository scan passed, repository policy: `eligible_for_demo_only`.
8. Review trust unverified: `hold`.
9. Conflicting CI observations: `hold`; the failure reason is not erased.
10. CI skipped: `hold`; skipped execution is not passed verification.
11. Future-dated evidence: `hold`.
12. Review for another repository: `hold`, even with the same head SHA.
13. GitLab-labeled synthetic candidate: same normalized contract and checks.

The final case demonstrates data-contract portability, not live GitLab support.
Tests also cover self-review, open findings, malformed input, duplicate JSON
keys, unsafe exclusions, unsupported methods and output overwrite protections.

The runner accepts only the bounded synthetic contract. Unknown fields and
live-data provenance are rejected before artifacts are written. Error messages
use fixed codes and never echo rejected content. Existing output directories
are not overwritten, and output must stay inside the local `out/` directory.

## Inspect and reproduce the evidence

Open the emitted `report.md`, then follow `recommendation.json` to a control,
requirement and evidence ID in `evaluation.json`. Its evidence digest links to
the retained normalized input; policy and effective-policy fingerprints are
also retained. `artifact-hashes.json` covers the emitted JSON content.

[examples/](examples/) contains the measured summary and retained bundles for
the required scenarios. A bundle stores each artifact under its normal file
name. Running the walkthrough produces those artifacts as individual files.
Timestamps and measured latency can vary; expected decisions and content
bindings must reproduce.

## Boundaries

This is a fixture evaluator, not a production merge controller or a general
Gemara policy engine. Supported control IDs, methods and scope are deliberately
closed. Unknown rules require implementation and tests before they can pass.
The ten-minute freshness limit is a demo setting, not a Fullsend-wide policy.

Real adapters must authenticate review producers and actors, fetch complete
current evidence, verify the authoritative candidate and trusted policy source,
and support final SCM revalidation. A source digest proves content identity,
not source authority. Risk classification and a complete MVE contract are not
implemented. No schema-valid document or passing fixture can grant a merge.

See [security boundaries](SECURITY.md), [findings](../../docs/attempts/02-policy-evaluation/FINDINGS.md),
the [work log](../../docs/attempts/02-policy-evaluation/WORKLOG.md),
and [the ADR amendment proposal](../../docs/attempts/02-policy-evaluation/ADR-PROPOSAL.md).
