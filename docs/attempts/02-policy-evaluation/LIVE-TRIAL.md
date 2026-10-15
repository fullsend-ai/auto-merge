# Follow the live Fullsend + Gemara example

This is a **shadow experiment**, not an autonomous merger. It separates three
questions: does the PR satisfy the candidate policy, is the repository qualified
for autonomy, and does the combined gate allow proceeding? Every result forbids
mutation. A passing candidate cannot override missing readiness evidence.

## Verified hosted example

Both final runs passed on source `0b0258cd1aa513cd41fdbc2bf15b70066f8722c0`:

- [Native fixture suite](https://github.com/fullsend-ai/auto-merge/actions/runs/38739049643):
  **46 Python tests**, the native SDK build/Go tests and synthetic replay passed.
- [Complete live verification](https://github.com/fullsend-ai/auto-merge/actions/runs/38739054288):
  **#28 candidate eligible; #29 candidate held**. Repository readiness and the
  combined gate held for both; all outputs forbade mutation.
- [Official Fullsend Review](https://github.com/fullsend-ai/auto-merge/actions/runs/38737376370)
  supplied the real approval, finding ledger and revision-bound lab risk receipt.

This completes the live shadow example. It does not qualify the repository for
production autonomous merging. The readiness holds below are deliberate controls,
not missing risk data or a failed evaluator.

## The real trial PRs

- [PR #28](https://github.com/fullsend-ai/auto-merge/pull/28) is the positive
  documentation-only case. Its head is
  `ecf653b90ded754640eabe9dc9b8a845066e7e11`.
- [PR #29](https://github.com/fullsend-ai/auto-merge/pull/29) intentionally violates
  the document contract. Its head is
  `3620abed828a904b52f0cb79a946f8b67500c13e`. The failed CI must hold this PR.

The live verifier expects #28 to pass every candidate assessment and #29 to fail.
It also expects repository readiness and the combined gate to remain held. Neither
trial PR is enrolled for auto-merge or intended to be merged.

## Verified producer and native result

[Official Fullsend Review run 38737376370](https://github.com/fullsend-ai/auto-merge/actions/runs/38737376370)
succeeded using configuration `ac36da8175ca4b3ad67b5aa82ed2a73a6b2380e6` and
published the head/config/run/attempt-bound risk receipt in
[the Review summary](https://github.com/fullsend-ai/auto-merge/pull/28#issuecomment-6182507614).
Local native verification then passed both real cases: #28 candidate `eligible`,
#29 candidate `hold`, repository readiness and combined gate `hold` for both.

The live run exposed an important collector correction: GitHub's PR `base.sha`
can be an older snapshot. The observer now reads the actual `main` branch head,
uses its configuration and rechecks it for movement. The older snapshot is
reported separately. Regression tests cover both a stale snapshot and an advancing
target branch; the evidence checks are not relaxed to accept an old configuration.

## What runs, and why

1. **Official Fullsend Review** performs the review and risk assessment. This lab
   uses the documented [harness composition mechanism](https://github.com/fullsend-ai/fullsend/blob/02438e1c117d31bf50f9fb9fafabe40856dbfdda/docs/guides/user/customizing-agents.md#configuration-with-base-composition),
   with a pinned official Review base and one host post-script override. There is
   no custom merge model or alternative policy engine.
2. **The host receipt extension** retains the official bundled post-script and
   adds one small, pinned patch. It publishes a versioned risk receipt beside the
   official findings ledger. The model cannot supply this receipt: the host strips
   model copies before adding its own. Missing, degraded or inconsistent risk has
   no receipt. This is a lab extension, not an upstream Fullsend feature.
3. **The read-only observer** verifies GitHub/Fullsend evidence and normalizes it
   into bounded values. It never executes PR code or retains review prose. It
   verifies the exact head, producer identity, completed run/attempt, trusted-main
   configuration and host source blobs before accepting a risk receipt.
4. **Native Gemara evaluation** resolves the control catalog and imported policies,
   runs the declared assessment plans and emits native EvaluationLogs. The glue
   collects facts; Gemara expresses and evaluates the policy requirements.
5. **The combined gate** keeps qualification separate from candidate eligibility.
   Unknown readiness still holds. There is no merge writer or authoritative
   eligibility-status publisher in this experiment.

The executable boundary lives in `sdk/main.go` because policy documents cannot
fetch and authenticate forge evidence themselves. It uses the native Go SDK and
its assessment/evidence records; it is not a replacement for Gemara. The supported
policy subset is [explicitly documented](../../../experiments/autonomy-platform/README.md#supported-policy-semantics).
Unsupported semantics hold rather than being silently ignored.

## Read these three policy files

- [Control catalog](../../../experiments/autonomy-platform/policies/controls.json):
  repository-readiness and candidate requirements.
- [Common policy](../../../experiments/autonomy-platform/policies/common-policy.json):
  imports the catalog and declares native assessment plans, including risk <= 2.
- [Repository policy](../../../experiments/autonomy-platform/policies/repository-policy.json):
  imports the common policy and adds a documentation-only assessment plan.

All three use official Gemara v1.5.0 schemas. Child plans add restrictions; they
cannot erase a failed common assessment. These are draft lab policies, not an
approved Red Hat standard.

## Run the complete verification

Follow [setup](../../../experiments/autonomy-platform/README.md#run), then:

```sh
python3 experiments/autonomy-platform/verify_live_trial.py
```

Or dispatch **Autonomy shadow observation** on main with `pr=28` and
`verify_example=true`. Read its Summary, not just the workflow's green check.
The verifier requires a stable, complete collection, all positive candidate
assessments passed, the negative CI failure detected, readiness held, and no merge
authority. Unexpected results fail the verification instead of weakening policy.

For an individual report:

```sh
python3 experiments/autonomy-platform/github_observe.py --pr 28
python3 experiments/autonomy-platform/github_observe.py --pr 29
```

The separate fixture workflow runs native tests and six explicitly synthetic
scenarios: satisfied, failed CI, missing review, stale review, wrong revision and
repository-policy restriction. Fully supplied synthetic readiness can produce
`would_allow`; it is not represented as real qualification evidence.

## Evidence and trust boundaries

- **Findings:** the official
  [v2 projection implementation](https://github.com/fullsend-ai/agents/blob/a159f388364279487818325ef5d3cc1bcd31e1ea/scripts/post-review.sh#L1974)
  retains the finding ledger and dispositions, and suppresses unsafe projections.
  The observer requires the pinned bot ID/login/type, explicit current head,
  matching approval and current summary. Any open finding, including info, holds
  conservatively. Sticky history, malformed markers and duplicate JSON cannot pass.
- **Risk:** the official legacy risk comment lacks a head binding. The lab's
  [small host extension](../../../.fullsend/scripts/review-risk.patch) adds a receipt
  containing only head, score/level, configuration and run/attempt IDs. The
  [pinned loader](../../../.fullsend/scripts/post-review-gemara.py) verifies the
  original script, patch and resulting script hashes. The receipt is not a signed
  production attestation; the observer independently checks its GitHub provenance.
- **Merge route:** [PR #27](https://github.com/fullsend-ai/auto-merge/pull/27) and
  [its successful merge-group run](https://github.com/fullsend-ai/auto-merge/actions/runs/38665663244)
  demonstrate the route. The merged SHA, workflow, producer and current required
  checks must match. Current CI/validator blob hashes must match the proof's
  sources; changes invalidate it. This historical proof grants no PR authority.
- **Collection stability:** PR revision/base, rules, reviews, comments and CI are
  checked again. A changing or incomplete collection holds. Native evaluator and
  validator children receive clean environments without forge credentials.

The observer reads public API metadata, including producer run metadata. It does
not read workflow logs, download output artifacts, post statuses/comments, change
rules or merge. Reports discard raw bodies, patches, finding anchors and actor
identities. Only the ordinary official Review host retains its existing write
permissions to publish review results.

## Why readiness still holds

These are real assurance requirements, not booleans to fill to obtain a green run:

- **Test sufficiency:** an owner-accepted assessment for the allowed change class.
  The toy validator proves its document contract, not general test quality; the
  delayed CI job intentionally repeats the same validator.
- **Runtime isolation:** evidence about the deployed Review runtime and its actual
  credential/network boundaries. A pinned image or a passed evaluator-environment
  test alone is not that assurance.
- **Trusted publication:** an approved authoritative publisher with protected
  producer binding. A successful read-only observation job is not an eligibility
  authorization check.
- **Shadow history:** accepted outcomes and explicit human promotion criteria.
  Two diagnostic PRs do not establish a sufficient safety record.

Gemara records and evaluates these requirements; Fullsend and repository owners
must supply the evidence and approve promotion. The complete example demonstrates
that both positive candidate evaluation and conservative readiness holds work.
It does not claim production qualification or implement automatic promotion.

## Historical proof

Earlier native-policy runs used source `6d1fe8e025b8ba245921f444d3bc089f92e1ee59`:
[fixtures](https://github.com/fullsend-ai/auto-merge/actions/runs/38720142221),
[#28 observation](https://github.com/fullsend-ai/auto-merge/actions/runs/38720146279),
[#29 observation](https://github.com/fullsend-ai/auto-merge/actions/runs/38720149623).
Those earlier runs held on missing findings/risk and readiness. They do not prove
this later risk extension. The append-only [worklog](WORKLOG.md) records the steps,
source revisions, validation and publication protections.
