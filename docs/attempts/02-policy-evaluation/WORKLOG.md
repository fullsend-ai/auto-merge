# Attempt 2 work log

This log contains public-safe commands, observations and decisions. It excludes
credentials, environment dumps, private ticket content, identities and API/event
payloads. Inputs and retained outputs are synthetic unless explicitly stated.

## 2026-10-14 — establish the experiment boundary

- Created an isolated local branch from Attempt 1 commit `c06d5b8`.
- Read the repository instructions, documentation hub and current gate boundary.
- Preserved the original document paths and recorded a commit-bound baseline.
- Kept existing `.github/` workflows and `.fullsend/` agent execution unchanged.
- Selected a local, fixture-only evaluator. It has no forge or model client,
  cannot merge, and does not invoke the existing finalizer.
- Inspected official Gemara schemas at `v1.6.0` / `14a8b1c02e1b7152781c0af7b6bcd07012f9763c`.
  ControlCatalog and EvaluationLog are stable there; Policy and EnforcementLog
  are experimental. Schema validation and policy evaluation are distinct jobs.
- Selected CUE `v0.17.1` with a pinned release-archive digest. Schema files are
  vendored with their license and hashes so validation can run offline.

Public references: [Gemara schemas](https://gemara.openssf.org/schema/),
[Gemara FAQ](https://gemara.openssf.org/faq/),
[Attempt 1 source](https://github.com/fullsend-ai/auto-merge/tree/c06d5b8ba0f1be703ed83415986c179d97f3329c).

## 2026-10-14 — implement and inspect the demo

- Added an actual Gemara ControlCatalog, two Policy profiles, normalized
  synthetic evidence, a custom deterministic evaluator and validated
  EvaluationLogs. Recommendations always permit no mutation.
- Implemented candidate binding, logical freshness, assumed fixture trust,
  independent review and open-finding checks. Missing, conflicting, skipped,
  unsupported and untrusted evidence hold rather than pass.
- Added two synthetic review-provider mappings and a GitLab-labeled fixture.
  These exercise the contract, not live provider authentication or integration.
- Retained input, effective policy, control/requirement/evidence mappings,
  content digests, evaluator source hashes, tool pins and measured results.
- Compared plain JSON with validated Gemara output using the same rules. This
  measures representation costs; it is not an independent correctness test.
- Prepared findings and a separate ADR amendment proposal. The public ADR
  [PR #7151](https://github.com/fullsend-ai/fullsend/pull/7151) remained open and
  unmerged at head `84070f941acd6abd8d2b1c0ea663dbd550a2612a` when checked.
  No upstream ADR was modified.

### Corrections and decisions discovered during implementation

- Official Policy validation rejected an empty optional `exclusions` array.
  Removed that field from the repository profile; both profiles now validate.
- A structurally valid policy can exclude Review. The custom resolver rejects
  that policy with `minimum_control_removed`. Schema validation is not enforcement.
- Added validation of the effective-policy boundary after self-review: empty
  control sets, removed minima, extended freshness and mutation-enabled models
  cannot reach an all-passed recommendation.
- Bounded file reads before JSON parsing, rejected nonregular inputs and
  duplicate JSON keys, and limited record fields and counts. Rejected input
  is not echoed into diagnostics or retained outputs.
- Kept CUE diagnostics private to the subprocess, passed only a fixed PATH and
  locale, and verified the executable and vendored schema hashes before use.
- Output writes require a new directory inside ignored `out/`; existing data,
  symlinks and control/schema locations are rejected.
- Kept target-branch SHA, cumulative merge-group identity, live evidence
  authentication and complete risk/MVE contracts as explicit gaps. Fixture
  trust markers and hashes do not establish real source authority.

## Verification record

Commands below run from the repository root. Bootstrap was the only demo setup
step that downloaded a tool; its pinned official archive and binary hashes
were verified. Validation and evaluation used local files.

```sh
python3 experiments/gemara-spike/bootstrap_cue.py
python3 experiments/gemara-spike/validate.py
python3 -m unittest discover -s experiments/gemara-spike -p test_spike.py
python3 experiments/gemara-spike/verify_legacy.py
python3 experiments/gemara-spike/demo.py
python3 experiments/gemara-spike/walkthrough.py
ruff format --check experiments/gemara-spike --exclude vendor
ruff check experiments/gemara-spike --exclude vendor
python3 experiments/gemara-spike/public_check.py
git diff --check
```

- **26 spike tests passed.** Coverage includes malformed input, protected
  minima, incorrect binding, freshness, trust, conflicting evidence, provider
  mappings, official schema rejection, clean validator environment, redacted
  errors and protected output locations.
- **43 existing mocked unit tests passed** with real processes and socket
  connections denied. The agent, dispatch harness and credentialed workflows
  were not run. These legacy tests require their existing YAML/JSON-schema
  packages; the spike evaluator itself uses Python's standard library.
- **13 evaluations produced the expected decisions.** Required satisfied,
  failed, missing, stale and repository-specific scenarios are retained in
  seven full synthetic bundles. Their artifact/source hashes and all official
  catalog, policy and evaluation schemas were checked after recording.
- Latest retained one-machine medians: evaluation **0.100 ms**, catalog/policy
  validation **51.657 ms**, evaluation-log validation **27.170 ms**. Plain JSON
  was **108 bytes** and the Gemara log **4,378 bytes** at the median. These are
  demonstration measurements, not production benchmarks; LLM calls were zero.
- Recorded **54 output frames** from actual controlled demo execution. The
  offline HTML player passed Next, Play, Pause, Show all and Reset checks;
  displayed text matched the recording, links existed, and no page errors or
  external page requests were observed. Its reading pace is separate from the
  terminal recording's actual timing.
- Formatting, lint and whitespace checks passed. Local links in new attempt
  documentation passed. The bounded public-content check found no flagged
  secret patterns, internal URLs or private home paths in the changed files.
  This is a limited check, not a comprehensive secret-audit guarantee.
- Attempt 1 workflow, agent, security contract, tests and example change remained
  unchanged; original document hashes matched the commit-bound baseline.

No commit, push, PR creation, workflow dispatch, live merge, model request,
live evidence collection or result upload was performed. Any later integration
must review the existing credentialed workflow boundary before triggering it.

Human review entry points: [demo instructions](../../../experiments/gemara-spike/README.md),
[recording](../../../experiments/gemara-spike/walkthrough.html),
[findings](FINDINGS.md), [ADR proposal](ADR-PROPOSAL.md) and
[security boundaries](../../../experiments/gemara-spike/SECURITY.md).

## 2026-10-14 — revise the platform scope before live integration

- Revisited the podcast's qualification, four-choice, trusted-policy and
  optional-observer sections. Kept its proposed behavior separate from shipped
  Fullsend features. The custom agent is not the next integration's center.
- Read public Fullsend source at `f5934f595239c5c9bb589f9d8e6a3f30a58945d8`:
  vision/readiness, forge/credential boundaries, managed per-repo configuration,
  tenant direction and vendored installation. No customer or private applied
  data was used. A temporary source checkout was used only for reading.
- Read public go-gemara source at `5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2`.
  Its assessment, evidence-capture, aggregation and bundle helpers are candidates
  for reuse. No SDK code or third-party evaluator was executed.
- Recorded the SDK's v1.5.0 schema declaration versus the PoC's v1.6.0 pin as
  a compatibility question. Also recorded the OSPS human-approval conflict,
  effective-policy semantics and successful-merge receipt mapping as questions.
- Added [SPIKE-PLAN.md](SPIKE-PLAN.md) and updated the local findings/ADR proposal.
  The plan separates repository qualification from candidate eligibility, and
  autonomy mode from engine selection. It includes shared/repo policy authority,
  an independent adapter comparison and secure vendored tests.
- Existing Python is explicitly scaffolding. The plain-format comparison is
  not claimed as an independent policy-engine interchangeability test.
- No runtime, agent, schema, fixture, retained result or workflow was changed
  in this scope revision. No installer, workflow, model or live merge ran.

Validation: checked new relative links, immutable public source targets against
the downloaded snapshots, public-content boundaries and whitespace. Existing
executed scenario results and test counts are unchanged by these document edits.

## 2026-10-14 — execute the platform experiments

Implementation and evidence:

- Added `experiments/autonomy-platform/`. Qualification and candidate
  eligibility share a bounded adapter contract, but bind different subjects.
  Off, Shadow, Light and governed policy are separate from engine selection.
  Every mode has no authorized actions and permits no mutation in this lab.
- Pinned native go-gemara module
  `v0.11.1-0.20261009030221-5e33fda460a8` with Go module checksums. A clean
  environment builds it with telemetry and automatic toolchain download off.
  The adapter uses native assessment execution, evidence capture and control
  aggregation. Its runtime receives only PATH and locale, never the API token.
- Added an independent Python adapter with native JSON predicates. It does
  not call the SDK or CUE. Shared/repo composition supports only the documented
  closed lab subset; it is not a replacement general Gemara policy language.
- Executed **20 synthetic mode/adversarial cases** across the two adapters.
  Missing Review, failed CI, changed configuration, expired qualification,
  protected policy changes and out-of-scope Light candidates hold. Tests also
  cover head/base/repository identity, source trust, future observations,
  policy weakening, new requirements and adapter-change invalidation.
- Native SDK catalog/Policy/evaluation packages validate against the pinned
  v1.6.0 schemas for the exercised readiness and candidate assessments.
- Reproduced a real limit: a valid generated Policy round trip through native
  `gemara.Policy` adds default structures and fails v1.6.0 validation. The
  compatibility test records the rejection; it does not silently remove fields.
  See [the reproducer](../../../experiments/autonomy-platform/SDK-COMPATIBILITY.md).
- Verified that the public lab had **no open PRs** and main remained `c06d5b8`.
  Used **closed PR #26** for a historical read-only collection experiment.
  Its real Fullsend Review metadata was observed; both engines held. This is
  neither an active PR trial nor a reconstruction of its historical merge.
- The GitHub collector uses fixed-host GET requests, no redirects, bounded
  responses and complete pagination. It never reads workflow logs or downloads
  artifacts. Only normalized booleans/classes/hashes and reasons are retained;
  review text, patches, actor identities and raw API/event payloads are excluded.
  Findings, trusted risk, runtime assurance, meaningful test sufficiency and
  promotion history remain unknown rather than being fabricated from green CI.
- Exercised Fullsend's own vendor collectors and both routing renderers at
  source `f5934f5`. **41 content files** were staged into ignored local output
  and hashed. Vendored dispatch resolves locally; layered dispatch retains its
  pinned upstream reference. No Fullsend binary was packaged and no installer,
  staged workflow or deployed vendored runtime was executed.
- Prepared local disabling changes: `enabled: false` for the legacy custom
  agent and a constant false guard on its supplementary semantic-context job.
  Preserved the old agent and scripts. Added a separate pinned fixture-only CI
  definition with contents:read, no secret/OIDC access, no persisted checkout
  credential, no cache or upload, and no live observer or merge operation.
- Read-only launch inspection confirmed these changes are **not on remote
  main**. A setup PR's edits cannot protect it from the base branch's legacy
  dispatch path. Active testing therefore requires a controlled publishing
  transition and explicit Git permission; no setting was changed here.

Corrections made during execution:

- The initial generated control catalog used the old applicability group;
  changed it to the actual lab applicability and meaningful per-control text.
- The vendor probe's temporary module initially could not resolve Fullsend's
  nested mintcore module. Mapped that module to the same approved source and
  successfully reran the native collectors without modifying the source tree.
- A strict round-trip equality test exposed SDK-added empty structures. Kept
  the actual schema rejection as a documented limit instead of normalizing it
  away or advertising general compatibility.

Reproducible commands, from repository root:

```sh
python3 experiments/autonomy-platform/build_sdk.py
python3 experiments/autonomy-platform/build_sdk.py --offline
python3 -m unittest discover -s experiments/autonomy-platform -p 'test_*.py'
python3 experiments/autonomy-platform/demo.py
python3 experiments/autonomy-platform/github_observe.py --pr 26
python3 experiments/autonomy-platform/launch_check.py
python3 experiments/autonomy-platform/prepare_vendor.py --fullsend-source /path/to/approved/fullsend
python3 -m unittest discover -s experiments/gemara-spike -p test_spike.py
python3 experiments/gemara-spike/verify_legacy.py
python3 experiments/gemara-spike/public_check.py
git diff --check
```

Verification: **28 platform Python tests, 4 native Go tests, 26 earlier spike
tests and 43 legacy mocked tests passed**. The legacy suite again denied real
process and network operations. Formatting, lint, local links, artifact/source
hashes, official schema validation, fixture workflow structure/permissions and
the bounded public-content scan were checked. The public check now explicitly
allows only the exact legacy-disabling edits and pinned fixture workflow;
other existing execution/security files remain protected.

Retained review entry points:
[platform instructions](../../../experiments/autonomy-platform/README.md),
[synthetic results](../../../experiments/autonomy-platform/examples/platform-results.json),
[historical observation](../../../experiments/autonomy-platform/examples/github-observation.json),
[vendor preparation](../../../experiments/autonomy-platform/examples/vendor-preparation.json).

Still pending: publishing/reviewing the setup, active Fullsend PR/workflow
testing, authenticated production evidence and a complete native merge/queue
lifecycle. The optional model observer remains deferred. No commit, push,
settings write, PR/comment creation, workflow dispatch, model call, live merge
or result upload was performed.

## 2026-10-14 — authorized setup publication

- Received explicit authorization to pause legacy dispatch, commit/push the
  setup branch and open a draft PR for human review. This does not authorize
  merging the setup, restoring dispatch or enabling autonomous merging.
- Verified the public repository, administrator access, allow-list membership
  and unchanged main at `c06d5b8ba0f1be703ed83415986c179d97f3329c` before writes.
- Disabled only `.github/workflows/fullsend.yaml` (workflow `365189947`) and
  `.github/workflows/auto-merge-context.yml` (workflow `365630785`) through
  repository workflow settings. Read-back confirmed `disabled_manually` for
  both. CI and Prioritize settings were not changed.
- Checked queued, in-progress, waiting, requested and pending run states before
  and after the pause; no active runs needed cancellation.
- Prepared the DCO-signed setup on `spike/gemara-policy-evaluation`. The draft
  PR is the human review surface and carries the immutable head and CI status.
  The fixture-only CI is permitted to run; no live observer or agent is invoked
  by that workflow. No merge, model run or result upload is part of publication.

Keep both legacy dispatch workflows paused until the trusted-main disabling
changes have been reviewed and landed by a human. Restore ordinary Fullsend
Review dispatch only after checking the trusted configuration and active runs;
the legacy auto-merge registration and context route must remain disabled.
Then create a harmless active PR for the separately reviewed shadow experiment.
