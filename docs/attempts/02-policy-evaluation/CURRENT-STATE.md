# Current state: Fullsend + Gemara auto-merge lab

Updated **October 19, 2026** for the prepared post-script-only producer. Local
validation is recorded in WORKLOG.md. Deployment and a fresh hosted v2 Review
must be verified separately; the hosted proof below remains the historical v1 run.

## What this repository is

A public integration lab for Gemara-backed auto-merge policy, Fullsend Review
evidence and GitHub enforcement. The custom auto-merge model agent from
[Attempt 1](../01-agent-led/README.md) and its supplementary context route are
disabled. The active review agent is Fullsend Review. General production readiness
is **hold**; the draft lab policies are not an approved Red Hat standard.

## Responsibilities and execution

1. **Fullsend Review** produces a review outcome, findings and ordinal model risk.
2. **The trusted host publisher** emits a bounded native Review record, with
   repository/head/base/configuration and run/attempt bindings; no model prose.
3. **The collector** authenticates GitHub publication metadata, checks the subject,
   expected host/source pins, integrity, completion and freshness.
4. **Native Gemara assessments** evaluate the catalogs and common/repository policies
   and emit EvaluationLogs. Named executable methods remain integration code.
5. **A separate writer** re-evaluates the owner-enabled pilot and requests exact-head
   queue entry using a dedicated lab App.
6. **GitHub's protected queue** tests the composed revision and requires the Gemara
   queue gate before GitHub merges.

The newest native-artifact proof reaches step 4 and holds. The earlier receipt
path demonstrated all six steps. These are separate proofs.

The active configuration now uses the existing Review `base:`/`post_script`
override with a Python publisher and normal upstream runtime installation.
The custom binary and its build/vendor manifests are removed. The pinned wrapper,
artifact upload and independent source/context checks remain. See
[post-script publication](POST-SCRIPT-REVIEW-EVIDENCE.md). This is a repository-local
integration, not a centrally shipped Fullsend evidence feature.

## Verified hosted proof

### Earlier complete protected merge — PR #41

- [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41), reviewed head
  `a44ea589d4ca2820cf7bf441705ffef65ff564c2`, merged October 16, 2026 at 12:31:20 UTC.
- [Writer run 38900418833](https://github.com/fullsend-ai/auto-merge/actions/runs/38900418833): evaluation and App writer succeeded.
- [Queue gate run 38900537957](https://github.com/fullsend-ai/auto-merge/actions/runs/38900537957): required Gemara gate succeeded.
- The lab App entered the queue without a manual review command or queue retry.
  [Retained identifiers](history/pr41-proof.json) explicitly state that this did
  **not** use the new native evidence publisher.

### Native publisher and automatic consumer — PR #43

- [PR #43](https://github.com/fullsend-ai/auto-merge/pull/43), exact head
  `d7383caff19e3b8e69eb76e72f7b99e99faf30c0`, base/configuration
  `98368f73467b8ea3353e5fc7ba363788499d6a09`.
- [Hosted Review run 38993688485](https://github.com/fullsend-ai/auto-merge/actions/runs/38993688485), attempt 1:
  successful vendored execution and exact-head approval; approximately 26 minutes.
- Native artifact `fullsend-review-evidence-1`, ID `12086559170`; payload SHA-256
  `e058b8f40e3e55556e446f19e3502b272189a953c914bcb22c9de564f969232a`.
- [Automatic Gemara shadow run 38995415634](https://github.com/fullsend-ai/auto-merge/actions/runs/38995415634),
  bundle `12086967236`: `review-evidence-reference.json` records `contract_verified`
  for the same record, subject, producer run and attempt.
- Fullsend approved with risk 1 (low), but retained an open low-severity
  `missing-doc` finding. AM-REVIEW and AM-RISK passed; AM-FINDINGS failed;
  AM-CLASS was unknown. Candidate and general readiness both held. No merge occurred.

An approval and a findings-policy pass are different facts. Any open finding holds
under this lab policy; that is our policy choice, not a universal Gemara rule.
The successful publication proves origin/context verification, not model accuracy.
See [the full hosted record](HOSTED-VENDORED-REVIEW.md) for the failure/fix history.

## Current pilot scope and protections

[Owner settings](../../../gemara-auto-merge/config/documentation-auto-merge-settings.json)
enable only ordinary modifications to `docs/example-feature.md`, at most 20 changed
lines, until **2026-10-22T18:00:00Z (October 22 at 2 p.m. EDT)**. Maintenance is disabled.
Settings are not a Gemara Policy. Workflow, policy, evaluator and configuration
changes cannot authorize themselves through this documentation cohort.

The writer uses a dedicated temporary repository-scoped lab App. Fullsend Review's
working authentication is distinct from the still-unresolved Fullsend-native
queue-writer credential handoff. No personal token is used by the pilot writer.

At the reviewed deployment, main had active queue/deletion/non-fast-forward rules,
no bypass actors, code-owner review and conversation-resolution requirements,
and four required checks: Example contract, Delayed integration (4 minutes),
Merge group proof and Gemara pilot queue gate. The general approval count was zero;
this is not a one-human-approval requirement on every PR. The queue handles one
entry at a time. The PR-stage queue check defers merge-group validation; a green
check on a PR is not permission to enroll it.

Owner bootstrap deployments used separately approved temporary exceptions and
restored protections. Those deployments are not autonomous merge proof.

## Readiness, modes and evidence lifetime

Candidate eligibility, repository readiness and action authorization are separate.
The bounded pilot is an explicit owner-enabled lab experiment while general
production qualification remains hold. It does not silently mark readiness green.
The retained native shadow evaluation left test sufficiency, isolation, accepted
history, trusted eligibility publication and qualifying merge-route evidence
unknown. A historical queue success does not establish every current assurance.

The local gate demonstrates Off (no evaluation), Shadow (observation), Light
(dependency-digest restriction) and Gemara-backed decisions. Shadow runs hosted;
Light is fixture-only and holds against this documentation-only repository policy.
These are not four finished Fullsend product switches. Policy-engine choice does
not itself confer merge authority.

Native records have a maximum 600-second evidence age. Old artifacts are useful
historical proof, not fresh authorizations. The native Review artifact expires
`2026-10-31T02:33:28Z`; the corresponding shadow bundle expires
`2026-10-31T02:34:25Z`. Their 14-day retention differs from ordinary Review logs.
A self-digest or bundle manifest is an unsigned integrity record, not a signature.

## Validation and remaining work

On October 18, the unchanged implementation passed 111 tests and all 15 native
producer-to-Gemara replay cases. Replay host inputs/publication proof are synthetic;
these are not 15 hosted Reviews. Fixtures cover altered/stale/wrong-subject evidence,
policy weakening, unsupported semantics, incomplete output and final action races.

Not yet established:

- A successful merge through the newest native-artifact route, with a matching
  current positive/negative pair and retained queue-stage evidence.
- General production qualification, accepted promotion criteria, model accuracy
  or a centrally approved auto-merge standard.
- A supported Fullsend installation/distribution interface, central policy trust,
  GitLab parity, arbitrary Gemara semantics or multi-entry queues.
- Rego, complyctl/ComplyTime or Privateer runtime-equivalence results. Those remain
  optional later comparisons; they are not dependencies of this demonstration.

The current native artifact collector selects automatic `pull_request_target`
runs. Command-triggered support in the older receipt verifier must not be assumed
for this newer route. Missing native evidence fails closed when the host lock is
installed; there is no fallback that silently accepts the old markers.

## Read next

- [Shadow walkthrough](SHADOW-OBSERVATION.md): follow the actual hold.
- [Pilot runbook](DOCUMENTATION-AUTO-MERGE-PILOT.md): authorization and queue checks.
- [Review contract](REVIEW-EVIDENCE-CONTRACT.md): what native publication replaces.
- [Implementation](../../../gemara-auto-merge/README.md): files, supported subset, setup and tests.
- [D1–D4 snapshot](D1-D4-REPORT.md) and [work log](WORKLOG.md): dated history, not a competing current guide.
