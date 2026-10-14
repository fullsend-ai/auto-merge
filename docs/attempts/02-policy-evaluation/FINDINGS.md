# Gemara capability assessment

Evidence status: local demonstration with synthetic input, plus separately
labeled primary-source documentation. The later platform phase also executed
SDK assessment, an independent adapter, historical public GitHub observation
and native vendor-content rendering. No active workflow, model or merge ran.

Scope update: this lab should investigate a reusable Fullsend autonomy-policy
integration, including qualification, four modes, shared/repo policy and engine
replacement. See the [platform experiment plan](SPIKE-PLAN.md). The Python
evaluator is experiment scaffolding, not a chosen general platform policy engine.

## Policy and controls — demonstrated

The demo's ControlCatalog, baseline Policy, repository Policy and EvaluationLog
validate against official Gemara `v1.6.0` schemas using CUE `v0.17.1`. At the
pinned commit, ControlCatalog and EvaluationLog are stable; Policy and
EnforcementLog are experimental. Pins and license are retained in the demo.

The baseline selects current CI and independent Review requirements. The
repository profile additionally selects a security-scan requirement. The same
evidence changes from demo-eligible to hold when that requirement is added.

Gemara represents imports, exclusions and assessment plans. The demo resolver
implements their effective meaning for three supported controls; it rejects
unknown scope, methods and overrides. It also enforces a local minimum floor.
A policy excluding Review still validates structurally, but our resolver
rejects it. Thus organizational restrictions on exclusions need trusted code
or a separate policy engine; schema validation does not implement them.

This is not a general resolver for all Gemara policy features. Arbitrary new
controls, exception workflows, threat models and organizational risk rules need
additional evaluators and governance. No Red Hat policy or internal data is
embedded here.

## Evidence and evaluation — demonstrated versus gaps

Thirteen evaluations cover the required satisfied, failed, missing, stale and
repository-specific cases, plus untrusted, conflicting, unsupported,
future-dated and cross-repository evidence. Self-review and open findings also
block in tests. Candidate identity includes forge, repository, proposal number,
head SHA, target ref and author; equal SHAs alone cannot cross repository bounds.

The custom evaluator performs these checks. CUE validates the resulting shape.
Fixture producer trust is explicitly assumed, not authenticated. No tool in
this demo collected current CI or proved a real Review identity. A label,
comment or fixture boolean must not become a production attestation.

Target-ref identity is modeled; target-branch SHA and cumulative merge-group
identity are not. Those require additional authoritative observations and
reauthorization.

The normalized records and effective-policy model form reusable boundaries.
Two synthetic provider formats map into the same Review record. A GitLab-labeled
fixture uses the same evaluator. This demonstrates representative mapping and
contract reuse; neither is a live adapter or a cross-forge integration proof.

## Decision and enforcement — demonstrated boundary

Only all satisfied required assessments yield `eligible_for_demo_only`.
Everything else holds. Unsupported requirements are rejected rather than
silently dropped. Recommendations explicitly permit no mutation. No model is
needed for these structured fixture cases.

The existing native SCM path remains responsible for mechanical enforcement
and the actual merge. This experiment cannot block GitHub on its own. Making a
result actionable requires trusted integration that publishes the right status
or requests the permitted native operation without bypassing repository rules.
Neither a schema nor an EvaluationLog supplies that integration.

Compared with a simple gate, Gemara supplies a portable artifact vocabulary and
control/requirement mappings; it does not improve the judgment represented by
the same inputs. The plain JSON comparison deliberately uses the same rules,
so equal decisions isolate format/validation costs rather than independently
proving correctness. Native controls already cover much mechanical policy.
The additional value must be policy reuse and evidence traceability, not a
second implementation of SCM protections.

## Traceability and audit — demonstrated

Retained bundles connect original synthetic input, content digests, catalog,
source policy, effective requirements, evaluator version, candidate, control,
assessment plan, evidence IDs, evaluation and recommendation. Run timestamps
describe actual local execution; freshness uses the labeled fixture as-of time.
These are reproducible records, not signed attestations.

Auditing an actual merge also needs authenticated source identity, authoritative
state observation, trusted policy provenance, request identity, queue revision
mapping, action/outcome linkage and durable storage. Digests cannot establish
authority by themselves. A successful merge receipt is not automatically a
Gemara EnforcementLog: its schema focuses on actions responding to
noncompliance, so the exact allow/merge mapping remains a design question.

## Compatible tools — documented, not run here

[Privateer](https://github.com/privateerproj/pvtr) is a plugin-based evaluation
framework. The [OpenSSF introduction](https://openssf.org/blog/2026/10/13/introducing-privateer-ai-assisted-security-compliance-evaluation-framework-joins-the-openssf-sandbox/)
describes deterministic assessments, optional AI, and OSPS Baseline repository
scanning. That supports evaluating it as an evidence producer, not assuming it
already verifies Fullsend's exact-candidate Review contract. No Privateer
plugin was installed or executed; auto-installing plugins and supplying live
tokens need a separate pinned-tool and permission assessment.

[OpenSSF Scorecard](https://github.com/ossf/scorecard/blob/main/docs/checks.md)
documents repository posture checks, including protection and review practices.
Those can contribute qualification evidence but do not replace a current,
authenticated semantic review of one candidate. No Scorecard scan was run.
Its [README](https://github.com/ossf/scorecard) describes platform-specific token
requirements and differences in check support. These are documented support,
not verified integrations in this lab.

The source-reviewed [Gemara Go SDK](https://github.com/gemaraproj/go-gemara/tree/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2)
also supplies assessment execution, evidence capture and aggregation helpers,
using caller-supplied checks. The later
[platform experiment](../../../experiments/autonomy-platform/README.md) executes
these helpers and compares an independent native-JSON adapter. SDK assessment
output passes the v1.6.0 schema for the exercised subset, but a native Policy
round trip adds default structures and fails that schema. This is a
[reproduced compatibility boundary](../../../experiments/autonomy-platform/SDK-COMPATIBILITY.md),
not proof of general compatibility between the SDK's v1.5.0 declaration and
our v1.6.0 schema pin.

The official [Gemara schemas](https://gemara.openssf.org/schema/) and
[FAQ](https://gemara.openssf.org/faq/) support artifact interoperability and
incremental adoption. Our executed integration uses these schemas directly.
We time-boxed plugin integration instead of treating unverified compatibility
as a completed feature.

## Adoption and portability

Upstream adopters would map local check names and review-provider outputs to a
shared evidence contract, choose applicable controls, and define trusted policy
sources and freshness requirements. Platform/provider adapters must implement
authentication, completeness and exact-candidate binding. This demo fixes those
choices for a small synthetic scope.

Organization-specific minima, allowed providers, stricter controls, exception
approval and maintenance belong in a separately managed trusted profile. The
spike's minimum-control rule illustrates that boundary; it is not a company-wide
policy. Additional domains can replace Gemara by supplying the normalized
effective-policy model and another result formatter while retaining the same
evidence checks. The later platform prototype demonstrates an independent
adapter using its own native JSON checks. It does not integrate an existing
third-party general policy engine or implement arbitrary Gemara Policy semantics.

Setup requires Python and a pinned CUE binary, plus reviewed schema updates.
The Python code adds no package dependency. Only bootstrap downloads a tool;
subsequent validation and evaluation run offline. The measured local summary
is retained in [examples/summary.json](../../../experiments/gemara-spike/examples/summary.json).
It records latency and artifact sizes; these are one-machine demonstration
measurements, not a production performance benchmark. There are zero LLM calls.

## Recommendation and follow-up

Use Gemara as an optional interoperable control/policy/evaluation layer around
a trusted evidence contract. Keep the evaluator, source authentication and SCM
authority explicit. Pin schema versions and treat experimental Policy features
as an adoption cost. A small custom evaluator is sufficient for the demonstrated
structured cases; this is not a decision to build a duplicate Fullsend policy
engine. Test existing SDK/evaluator capabilities and a replaceable adapter
boundary before choosing the platform implementation.

Before production use, implement authenticated adapters, define missing risk
and verification-sufficiency evidence, reconcile findings, specify queue-revision
reauthorization and durable outcome receipts, and review the credentialed
workflow boundary. Privateer can be investigated as an alternative evaluator
behind the same contract after its plugins and privileges are pinned.

The proposed ADR amendment preserves the authority boundary while allowing
the eligibility implementation to be selected from evidence. It does not make
Gemara mandatory or claim that this spike proves unattended merging safe.
