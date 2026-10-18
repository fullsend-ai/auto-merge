# D1–D4 implementation report

**Historical snapshot:** October 16, 2026, before branch publication and hosted
native proof. Later deployments supersede the pending/uncommitted statements
below. See [current state](CURRENT-STATE.md) and the
[successful hosted native trial](HOSTED-VENDORED-REVIEW.md). The original results
are preserved rather than rewritten as hosted evidence.

Date: October 16, 2026. Scope: `fullsend-ai/auto-merge` only.

## Historical local-validation status

D1–D4 are implemented and locally validated on `demo/gemara-evidence-d1-d4`.
This report records local validation before branch publication. Publication as a
PR does not deploy these changes; no new hosted run is claimed by this snapshot.
Main was independently checked at `89f5f2f507d936456439943cb696f45efa07dea1`;
its protections were active with no bypass actors. No repository setting or
credential was changed, and no upstream issue or PR was created.

The deployed bounded pilot already demonstrated automatic Review, App-backed
queue entry and a protected merge in [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41).
That historical proof is distinct from this branch’s new native evidence experiment.
General production readiness remains **hold**.

## D1 — Correct baseline and proof boundaries

- Corrected the stale claim that the dedicated App handoff was blocked.
- Corrected the repository instructions that incorrectly described this public lab as private.
- Retained [PR #41’s exact identifiers](history/pr41-proof.json), the
  [writer run](https://github.com/fullsend-ai/auto-merge/actions/runs/38900418833)
  and [queue gate](https://github.com/fullsend-ai/auto-merge/actions/runs/38900537957).
- Kept the earlier operator-assisted PR #30 as historical evidence. The
  Fullsend-native credential handoff is still separate from the dedicated lab App.
- Corrected schema/SDK terminology and documented the distinction between
  deployed behavior, local tests, synthetic evidence and proposed upstream work.

## D2 — Retained, understandable evaluation artifacts

Existing Gemara workflows now upload `gemara-evaluation-<job>-<attempt>` artifacts
for 14 days. No new workflow, permission or credential scope was introduced.
The job summary points to the artifact and distinguishes completion, policy
result and production readiness. The artifact contains:

- `decision.json`: repository/PR/revisions, stage, assessment results/reasons,
  effective-policy digests, implementation digests and native evaluator identity.
- Native `*-evaluation-log.json` files, including supporting readiness/candidate
  evaluations in the normal live path.
- `normalized-evidence.json`: normalized observations already present in those logs.
- `effective-policy.json`: the exact loaded catalogs and policies.
- `summary.md` and an unsigned SHA-256 `manifest.json`.

Partial/duplicate/inconsistent assessment logs cannot be exported as successful
results. Failure output contains stable error codes, not raw exception/API text.
A bundle is evidence of an evaluation, not a merge authorization or signature.
New hosted artifact upload behavior awaits deployment; local export is tested.

## D3 — Native Review evidence producer and consumer

A real Fullsend binary was built from pinned source plus repository-owned source
additions in an isolated copy inside auto-merge. No upstream checkout was changed.
Generated binary/source/cache files remain ignored. Default Review installation
and workflow pinning were not changed. This is an isolated binary experiment,
not a completed vendored installation or deployed native publication route.

The new command emits a bounded, versioned Review record. Its consumer requires
a separately supplied publication proof, expected subject and freshness/context
checks. It supplies AM-REVIEW, AM-FINDINGS and AM-RISK to native Gemara without
parsing comments. The [contract and ownership map](REVIEW-EVIDENCE-CONTRACT.md)
explain publication, invalidation, remaining checks, removable reconstruction
code and the implementation-ready Fullsend F1 handoff. No upstream issue was filed.

Fifteen end-to-end cases exercise the actual Fullsend binary and native Gemara.
Host inputs and publication proof are explicitly synthetic. The valid case is
eligible; wrong head/configuration, absent verification, alteration, forged
self-digest, stale/future evidence, supersession, cancellation, wrong attempt,
open findings, high risk, missing risk and rejected review all hold as expected.
Authentic high-risk evidence is still rejected by policy. Nothing grants merge
authority or certifies that the model’s conclusion is correct.

## D4 — Refusal coverage and final action checks

The suite includes 101 Python tests and executes the native producer’s Go tests.
Existing policy/forge tests were retained. New coverage includes:

- incomplete/inconsistent evaluation output despite successful execution;
- evidence identity, integrity, context, expiry, supersession and malformed data;
- empty, skipped and failed tests remaining insufficient for readiness;
- final enablement/expiry/configuration/head/base revalidation;
- duplicate events recognizing an already pending queue/auto-merge request, with
  one write across two sequential attempts; existing per-PR workflow concurrency
  serializes writers, and GitHub remains authoritative for queue enforcement;
- expected merge composition with a legitimate new base differing from the
  reviewed tree, while unrelated queue changes remain refused.

Unknown methods, weakened imported requirements, wrong-SHA CI, wider token
scope and changing API observations remain covered by existing tests. The
production queue still intentionally supports one PR, not arbitrary batching.

## Verification and remaining boundary

- Python suite: 101 tests passed; native producer Go tests passed.
- Actual local Fullsend build and offline rebuild: passed, including module
  integrity verification. All 15 producer-to-Gemara replay outcomes matched.
- Existing native-policy examples: expected results in all scenarios/modes.
- Read-only live observation of PR #36: stable collection, candidate/readiness
  and combined decision held; the new local bundle was generated successfully.
- Ruff, pinned actionlint, example-document validation and whitespace checks passed.
- Pinned Gitleaks v8.24.2: zero findings across proposed public files and generated
  contract/PR evidence (redacted scanning). Local documentation links validated.
- See [the validation receipt](history/d1-d4-local-validation.json) for tool pins,
  replay outcomes and the native binary/source identities.

Native production publication, authenticated retrieval and a full hosted
consumer integration are not established by synthetic proof. Test sufficiency,
isolation assurance and accepted promotion history are not made green by this work.
The pilot’s allowed file, line limit, expiry, disabled maintenance path and
main protections remain unchanged. Hosted checks begin after branch publication.
No merge, deployment or protection exception is authorized by this report.
