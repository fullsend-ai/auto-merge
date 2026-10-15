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

## Fullsend compatibility correction

Both initial Review jobs failed before publishing a review: the current Review
manifest required FULLSEND_APP_SET, but the older pinned reusable dispatcher did
not supply it. Updated only the immutable dispatcher pin to official Fullsend
commit 02438e1c117d31bf50f9fb9fafabe40856dbfdda, whose Review job supplies the
standard fullsend-ai default. Checked all existing shim inputs/secrets against
that revision: no unknown inputs/secrets or newly missing required fields. No
credential or authentication mode was changed.

## Readable live evidence

Both real CI runs completed: #28 succeeded and #29 failed as intended. Both
adapters agreed on the corresponding CI assessment and held overall. Hosted
observer runs also completed successfully, including automatic runs after CI.
Made unavailable observations absent rather than null, so assessment reasons
say missing instead of invalid_value; tests cover this distinction. Added
plain-language control names to summaries and a compact live-trial walkthrough.
Validation remains 26 Python tests plus the pinned build's 4 Go tests.

## Built-in provider migration

The refreshed Review reached provider creation but failed because the repository's
old reserved-name Vertex provider supplied _NOOP_VERTEX_AI, which the current
built-in profile does not declare. This matches upstream issue fullsend#8006.
Applied the official built-in-provider migration: bare vertex-ai name in the
disabled legacy harness, no copied built-in profile entry, removed both stale
provider/profile files, confirmed no sandbox GH_TOKEN entry exists. Original
Attempt 1 files remain recoverable through the immutable baseline commit. No
inference credentials, project, auth mode or model were changed.

## Verified final positive observation

After the documented migration, Fullsend run 38667018391 succeeded and its Review
bot approved PR #28 at ecf653b90ded754640eabe9dc9b8a845066e7e11. A stable
read-only observation returned no API errors; native Gemara and reference adapters
both passed CI, Review metadata, change class and governed-path predicates. Both
held overall with findings/risk and readiness assurance still missing. Dispatched
hosted observer run 38667624427 for that exact scenario. Negative PR #29 remains
unmerged with intentionally failed CI. No trial PR was queued for merge.

## Native Gemara rewrite (local preparation)

User requested removal of the alternative adapter and an end-to-end native Gemara
trial. Archived the comparison implementation locally. Removed its evaluator and
custom JSON profiles from the active path. Added official-schema ControlCatalog,
common Policy and importing repository Policy; a single native SDK evaluator
resolves imports/versions, scope, coverage, assessment plans and supported method
parameters. Child assessments cannot replace common ones. Unsupported semantic
features explicitly hold instead of being ignored. Native EvaluationLogs include
catalog, requirement and policy-plan references and pass output validation.

Selected official schema v1.5.0 to match the tested SDK's declared schema version.
CUE and schema archive/file hashes are pinned; dependencies live in ignored tools,
not a repository vendor tree. No Policy serialization round trip is required.
The historical SDK/v1.6 round-trip limitation is not claimed fixed.

Replaced comparison tests with native import, scope, schema, method, inheritance,
coverage, stale/missing/wrong-subject evidence and credential-isolation tests.
Added a compact six-case runnable synthetic replay and prepared trusted-main
workflow changes. No commit, push, rules change or workflow activation is part of
this local rewrite; those require this turn's explicit Git permission.

Validation: 30 Python tests, 4 native SDK Go tests, six replay cases and four
mode simulations passed. Local credential-free native observations of #28 and
#29 were stable and returned no API errors. #28 passed CI/Review; #29 failed CI;
both held on missing evidence. All native logs passed the matching official
EvaluationLog schema. Raw data and reports remain local/ignored, not committed.

## 2026-10-15 publication authorization

User explicitly authorized committing/pushing the native Gemara path and running
hosted tests and real-PR observations, including fixes justified by those runs.
Verified remote main still matches the prepared baseline. The existing GitHub
permissions and read-only observer boundaries remain in place; no merge authority
is being activated. Hosted proof is recorded separately after execution.

## 2026-10-15 hosted native-policy proof

Published native implementation 6d1fe8e025b8ba245921f444d3bc089f92e1ee59 to main.
The direct update needed a temporary admin exception; the original ruleset fields
were restored immediately and verified. No control was deleted or left bypassed.

Executed native fixture run 38720142221: passed 30 Python tests, the build's 4 Go
tests, six synthetic replay scenarios and four mode simulations. All native input
documents and generated EvaluationLogs were schema-validated against the pinned
official matching schemas. The complete synthetic case would allow a shadow
recommendation; failed, missing, stale, wrong-revision and stricter repository
cases held. Every output forbade mutation.

Native hosted observations 38720146279 (#28) and 38720149623 (#29) both completed
successfully on that exact source revision. Their normalized outputs report
stable candidates, hold decisions and mutation_permitted=false. #28 retains
Fullsend's approval for ecf653b90ded754640eabe9dc9b8a845066e7e11; #29 retains
the intentionally failing CI at 3620abed828a904b52f0cb79a946f8b67500c13e.
The native policy path consumes this Fullsend/GitHub evidence without a new model
agent or a comparison evaluator. It does not invent missing findings/risk or
readiness attestations to obtain a passing live decision.

Inspected only normalized result lines, test counts and job/check metadata. Raw
workflow logs and API bodies were not retained or published. The observer itself
never reads workflow logs. No test PR was merged or given auto-merge authority.
The remaining boundary is evidence production/assurance and promotion governance,
not whether the demonstrated native catalog/import/plan/evaluation path executes.


## 2026-10-15 evidence collection update

Verified live main 44ae8556011a65765c88335cee2500c9822319d3 and unchanged open
trial heads before editing. Inspected current official Agents source at
a159f388364279487818325ef5d3cc1bcd31e1ea and normalized public Review metadata.
Added consumption of its v2 findings ledger, pinned bot identity and exact head,
with safe closed-disposition handling and rejection of malformed/duplicate data.
Added historical queue proof with current rules and source-blob binding. Recheck
reviews, comments and checks during collection; a changed collection holds.

Local live native observations: #28 findings and queue evidence passed, risk
remained Unknown because the actual risk comment has no head binding. #29 queue
proof passed, but its intentional failed CI and absent Review still hold.
Both collections were stable with no API errors; mutation remained forbidden.
No reports retain comment bodies, file anchors, raw API payloads or identities.

Prepared a small producer-side risk receipt patch in the local research archive,
not in this public repository. Its shell syntax and ten actual jq projection
cases passed. This is proposed upstream work, not deployed support. No upstream
file or workflow was changed. Independent readiness assurances and human promotion
criteria remain required; none was fabricated from CI success or approval.

Validation: 39 Python tests cover native evaluations, real-source normalization,
ledger lifecycle and collection races. Prior pinned Go evaluator code is unchanged.
The evidence verification made no GitHub writes. Subsequent publication was explicitly
authorized by the repository owner; hosted producer/readiness work continues below.
