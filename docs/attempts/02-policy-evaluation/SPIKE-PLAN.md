# Platform integration questions and experiment plan

Status: platform experiments below have now been implemented locally; see
[executed results](../../../experiments/autonomy-platform/README.md). No feature
was deployed or upstream decision changed. Active PR/workflow testing remains
pending the trusted-main setup. No live merge is authorized by these results.

## The question this lab should answer

Can Fullsend use Gemara and its ecosystem for a reusable autonomy standard,
repository qualification and per-change policy evaluation, while accepting an
organization's alternative policy engine through the same platform boundary?

This fits Fullsend's [vision principles](https://github.com/fullsend-ai/fullsend/blob/f5934f595239c5c9bb589f9d8e6a3f30a58945d8/docs/vision.md#principles)
of earned autonomy and traceable decisions, and its
[repository-readiness problem](https://github.com/fullsend-ai/fullsend/blob/f5934f595239c5c9bb589f9d8e6a3f30a58945d8/docs/problems/repo-readiness.md).
It is a proposed platform direction, not evidence of an existing fleet service.

The auto-merge repository is a testbed for that question. Its custom agent is
Attempt 1, not the proposed center of the platform. An optional observer may
later compare its opinion with completed evaluations; it cannot turn a hold
into permission, access merge credentials or mutate the PR.

The supplied podcast distinguishes repository qualification from current
candidate eligibility, makes qualification expire when its assumptions change,
and places reasoning in Review or specialized verification. Its four user
choices are Off, Shadow, narrow autonomy and custom policy. These are proposals
in the podcast, not claims about shipped Fullsend settings.

## Four choices; policy engine is a separate choice

Proposed product behavior:

- **Off:** no Fullsend autonomous merge authority. Normal Review may continue.
- **Shadow:** evaluate readiness and qualifying candidates, retain decisions,
  and compare with human findings and later outcomes. No merge request.
- **Light / narrow autonomy:** an explicitly approved change class uses a
  published default profile. Readiness and candidate checks still apply.
- **Policy-governed:** centrally managed or repository-selected policy defines
  scope and additional requirements. It may be stricter than Light; it is not
  automatically a broader or less safe mode.

Gemara could support evaluation under Shadow, Light and custom policy. It is
not a compulsory fourth step. Choosing another engine must not require another
set of modes, a different merge controller or an artificial Gemara policy file.

## Two decisions that share evidence but have different subjects

**Repository qualification:** can this repository, branch and proposed change
class support autonomy under the current policy? Inputs include authoritative
rules, access to complete check/review data, meaningful verification for that
class, trusted status publication, execution isolation and native queue support
when required. Shadow outcomes can supply additional evidence. A percentage
coverage score or a green status alone is not qualification.

**Candidate eligibility:** does this exact revision satisfy the applicable
policy now? Inputs include current Review and findings, risk and verification
evidence, protected paths, the qualified scope and native forge constraints.
Repository qualification cannot approve all future PRs.

Both decisions can use Gemara controls and evaluation records. Qualification
must bind its scope, policy and observed configuration, expire or be revoked,
and report specific missing capabilities. Human promotion is a governance
decision; an evaluator should not invent its acceptance thresholds.

## What to reuse and what the platform must still provide

**Reuse Gemara where demonstrated:** catalogs, Policy artifacts, requirement
mappings and EvaluationLogs already validate in the fixture demo. Inspect
existing catalogs before authoring equivalent controls.

**Test Gemara SDK capabilities before duplicating them:** the reviewed
[Go SDK assessment code](https://github.com/gemaraproj/go-gemara/blob/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2/assessment_log.go)
executes caller-supplied assessment functions and captures their evidence;
[control evaluation](https://github.com/gemaraproj/go-gemara/blob/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2/control_evaluation.go)
aggregates assessments. Its
[bundle assembler](https://github.com/gemaraproj/go-gemara/blob/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2/bundle/assemble.go)
collects referenced artifacts. Assessment, capture and aggregation are now
executed in the platform phase; bundle assembly remains source-observed only.
Assembling dependencies is not proof of effective
policy semantics, trusted provenance or mandatory-control enforcement.

**Fullsend integration responsibilities:** collect and authenticate platform
observations, connect Review/verifiers, resolve trusted configuration, schedule
reevaluation, present mode/readiness explanations, validate the configured
engine's result contract, isolate credentials, and request the native SCM
operation only after final state revalidation. Existing forge, configuration,
mint, sandbox and observability paths are foundations; the complete autonomy
integration is not implemented by this spike.

**Organization governance:** own applicable controls, accepted risk, protected
classes, promotion criteria, exceptions and who may change policy. Fullsend
should not ship a duplicate business-policy interpreter beside the chosen
engine. It still cannot delegate away its credential and mutation boundaries.

**Native SCM:** remain authoritative for branch rules and permitted direct or
queue/train operations. A passing policy result cannot waive a human approval
or native requirement that the repository still enforces.

Gemara's [FAQ](https://gemara.openssf.org/faq/) describes connected tools that
produce evaluation records; it does not supply every platform-specific check.
The integration work above is not evidence that Gemara has failed to provide
its intended interoperability model.

## Central and repository policy without self-approval

Proposed contract, not currently accepted Fullsend configuration keys:

- Select a policy adapter and trusted, versioned policy sources independently
  from the autonomy mode. An adapter may use Gemara internally or retain its
  engine's native policy format.
- Combine an approved shared safety standard, organization requirements and
  repository scope. Do not assume normal configuration precedence proves that
  a mandatory minimum survives an override or exclusion.
- Resolve policy from trusted target-branch state or an independently governed
  source. A policy-changing PR uses the previously trusted version, requires
  appropriate governance, and cannot authorize itself.
- Return a bounded result for qualification or candidate eligibility: subject,
  evaluated state/configuration, source and effective policy identities, engine
  version, assessed mandatory requirements, evidence references, reasons and
  validity. Unknown, unavailable or unsupported required evidence prevents action.
- Keep authorization/action receipts outside the engine-specific format. The
  platform validates result provenance and operational invariants without
  re-running the engine's business rules. Another engine must satisfy the same
  safety contract; replacement is not permission to weaken it.

Fullsend already has managed per-repo configuration and shared presets. Current
[managed configuration code](https://github.com/fullsend-ai/fullsend/blob/f5934f595239c5c9bb589f9d8e6a3f30a58945d8/internal/repos/managed_config.go#L151)
resolves repository/forge/default settings over a preset. That provides a
distribution path, not a finished runtime autonomy-policy composition system.
[ADR 0123](https://github.com/fullsend-ai/fullsend/blob/f5934f595239c5c9bb589f9d8e6a3f30a58945d8/docs/ADRs/0123-tenant-configuration-from-repos-yaml.md)
reuses repos.yaml for future centrally managed tenants while leaving service
and infrastructure decisions open. Central policy therefore does not require
reviving the deprecated per-org installation mode.

## Experiments and the evidence each must produce

1. **SDK reuse and compatibility:** pin a supported SDK/schema pair; reproduce
   the existing satisfied/failed/missing/stale results using native assessment
   and aggregation helpers. Validate output against the selected official
   schema and record which custom code can be removed. Assessment/capture and
   aggregation have now been exercised; Policy round-trip incompatibility was
   reproduced. General policy resolution is not yet implemented.
2. **Repository qualification:** evaluate a small published readiness profile
   against representative observations. Remove check visibility, change rules
   or expire the observations; show qualification becoming unavailable with a
   precise reason. Do not claim fleet readiness from one repository.
3. **Four-mode behavior:** feed identical evidence through each choice. Prove
   Off and Shadow have no mutation path, Light respects its change class, and
   governed policy cannot remove mandatory conditions. Promotion is explicit.
4. **Policy authority:** test shared policy plus stricter repo scope, conflicting
   policies, attempted exclusion of a minimum, changed source policy and a PR
   modifying its own controls. Retain the effective-policy explanation.
5. **Engine replacement:** supply the same platform request to the Gemara
   adapter and an independent minimal deterministic adapter. Demonstrate the
   same subject/provenance/failure contract without requiring Gemara artifacts
   from the alternative. The current plain-JSON demo uses the same evaluator
   and does not prove this interchangeability.
6. **Real Fullsend Review in shadow:** after the trusted route is prepared,
   observe a harmless real PR in this repository. Assess actual CI, Review,
   unresolved findings and policy, then push another revision and demonstrate
   invalidation. Publish only allowlisted, bounded diagnostics. No live merge.
7. **Vendored platform experiment:** if core changes are needed, prepare the
   local source/binary/workflow bundle, record provenance and compare its
   behavior with the layered install. Test credential separation and trusted
   policy sourcing before activating the bundle. Do not install fleet-wide.
8. **Optional observer later:** record its additional hold opinion separately
   from authority; investigate disagreements against human findings and later
   outcomes. An opinion alone is not evidence that Review has a bug.

Live merge authorization is a separate follow-up after these results. It needs
authenticated evidence, authoritative base/cumulative queue revision binding,
final refresh, duplicate-run handling, native-policy compliance, postconditions
and durable receipts. A standalone CI check does not implement that lifecycle.

## Vendored testing and public-repository boundaries

[Vendored installs](https://fullsend.sh/docs/ADRs/0047-vendored-installs-with-vendor-flag)
support experimentation with local Fullsend source and a matching binary plus
workflow assets. A vendored marker selects content; it is not a trust boundary.
Privileged execution must use approved content from a trusted revision, never
the subject PR's modified workflows, policy adapters or executable hooks.

Prepare generated files and review their diff before any installer write.
Install commands can create commits/PRs or alter configuration and credentials;
they are not read-only build commands. Keep builds free of secrets, pin tools
and assets, scope the run to this lab, minimize result publication and disable
the legacy automatic merge route from trusted state before opening a live test.
No install, workflow, model or active candidate evaluation was run for this
plan. The executed GitHub observation is historical; the native vendor probe
stages content and compares routing without packaging a CLI or activating it.

## New questions raised by evidence

- **SDK/schema alignment:** the inspected SDK
  [version declaration](https://github.com/gemaraproj/go-gemara/blob/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2/version.go)
  is v1.5.0; our executed schema pin is v1.6.0. Which tested pair preserves all
  required semantics? Source inspection is not compatibility proof.
- **Human-approval conflict:**
  [OSPS-QA-07.01, baseline 2026-08-28](https://baseline.openssf.org/versions/2026-08-28#osps-qa-0701)
  applies at maturity level 3 and requires a non-author human approval.
  Which profiles must remain human-approved? Never count a bot as that human
  or claim full conformance while excluding the control without disclosure.
- **Policy semantics:** which existing Gemara-compatible evaluator implements
  scope, exceptions and protected minima correctly? The current Python subset
  is scaffolding for comparison, not the selected general platform engine.
- **Direction versus accepted design:** Fullsend's
  [roadmap](https://github.com/fullsend-ai/fullsend/blob/f5934f595239c5c9bb589f9d8e6a3f30a58945d8/docs/roadmap.md#auto-merge)
  still describes a dedicated agent. The deterministic-stage proposal follows
  this podcast and lab direction; it has not silently become the upstream plan.
- **Receipts:** how should a successful native merge map to Gemara artifacts?
  The [EnforcementLog](https://gemara.openssf.org/schema/enforcementlog.html)
  is experimental and describes responses to noncompliance. Preserve a truthful
  platform outcome receipt while investigating that mapping.

Source snapshot: Fullsend `f5934f595239c5c9bb589f9d8e6a3f30a58945d8`,
go-gemara `5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2`, reviewed 2026-10-14.
The supplied podcast remains the source of the four choices and qualification
proposal. Source-observed features, executed results and proposed work are
deliberately labeled separately.
