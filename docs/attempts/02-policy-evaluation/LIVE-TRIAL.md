# Follow the native Gemara trial

The native Gemara implementation is published on main. Verified hosted runs all
used commit `6d1fe8e025b8ba245921f444d3bc089f92e1ee59`:

- [Native fixture suite](https://github.com/fullsend-ai/auto-merge/actions/runs/38720142221):
  30 Python tests, the pinned build's 4 native Go tests, six replay cases and four
  mode simulations passed. Native input/output schema validation ran on the host.
- [PR #28 native shadow observation](https://github.com/fullsend-ai/auto-merge/actions/runs/38720146279):
  stable real-PR observation; native common and repository plans were evaluated;
  CI and exact-revision Fullsend approval passed; the overall decision held on
  missing findings/risk and readiness evidence.
- [PR #29 native shadow observation](https://github.com/fullsend-ai/auto-merge/actions/runs/38720149623):
  stable observation of the intentional CI failure; native evaluation held.

These are native-policy runs, with no alternative evaluator. A successful
workflow means the evaluation completed; the recorded policy decision remains
`hold`. Local credential-free observations independently produced the same
candidate outcomes with no API errors and schema-valid native EvaluationLogs.

## Local evidence collection update (not yet published)

The updated collector was run locally against the real PRs on 2026-10-15, with
native schema validation and no GitHub writes. These results do not describe the
older hosted runs linked above:

- **PR #28:** current Fullsend approval and the official v2 findings ledger pass.
  The ledger is in [Fullsend's review summary](https://github.com/fullsend-ai/auto-merge/pull/28#issuecomment-6182507614),
  explicitly bound to the same head as review 5527040782. Historical queue-route
  evidence also passes. Overall decision remains `hold`.
- **PR #29:** failed CI still holds; no complete current Review ledger is present.
  Queue-route evidence passes independently of candidate eligibility.
- **Risk:** #28 has a risk comment, but that comment does not identify its head.
  The collector reports `fullsend_risk_missing_revision_binding` and supplies no
  risk observation. #29 has no risk comment. Neither becomes a low-risk default.

`fullsend_evidence.py` consumes the official projection instead of analyzing
review prose. It requires the pinned bot ID/login/type, one explicit current head,
matching approval and a summary posted within five minutes before that review.
Any open finding, including informational findings, holds conservatively. Prior
closed findings remain represented; malformed/duplicate/unknown data holds.
Old sticky-comment history cannot satisfy a current observation. The collector
rechecks reviews, comments and CI before trusting the collection.

The queue proof is [PR #27](https://github.com/fullsend-ai/auto-merge/pull/27) and
[its successful merge-group CI run](https://github.com/fullsend-ai/auto-merge/actions/runs/38665663244).
It must match the merged SHA, official CI workflow and repository, current queue
rules and expected check producers. Its CI workflow and validator blob hashes
must still match current main. A changed source invalidates the historical proof.
This proves a route was exercised; it grants no merge permission to #28 or #29.
The proof IDs are this lab's inputs, not requirements for other repositories.

Verified producer references at
[Agents a159f388](https://github.com/fullsend-ai/agents/tree/a159f388364279487818325ef5d3cc1bcd31e1ea):

- [Runner projection and risk publication](https://github.com/fullsend-ai/agents/blob/a159f388364279487818325ef5d3cc1bcd31e1ea/scripts/post-review.sh#L1974)
  explain how the complete retained ledger is projected and unsafe projections
  suppressed. The separate risk comment is emitted near line 1678.
- [Review result schema](https://github.com/fullsend-ai/agents/blob/a159f388364279487818325ef5d3cc1bcd31e1ea/schemas/review-result.schema.json)
  describes findings, dispositions and risk returned to the host.

**New platform question from this evidence:** should Fullsend publish a
runner-owned, revision-bound risk receipt next to its findings projection?
A minimal producer patch is prepared locally outside this public repository.
It emits only version/head/score/level, excludes degraded or invalid assessments,
and strips model-supplied copies before adding the host's marker. It is a proposal;
the observer does not accept it as an existing official contract. Publishing and
running that producer change is necessary before a live risk control can pass.

The remaining readiness requirements need independent evidence:

- **Meaningful tests:** an accepted test-sufficiency assessment for the allowed
  change class. Passing the toy document validator does not establish broad test
  quality; the delayed job intentionally repeats that same validator.
- **Runtime isolation:** assurance about the actual Review runtime and its
  credential/network boundary, tied to the deployed configuration.
- **Trusted status publication:** an approved publisher and protected producer
  binding. This read-only observer deliberately has no status-write permission.
- **Shadow history:** accepted outcomes and explicit human promotion criteria.
  Two diagnostic PRs do not constitute a sufficient safety record.

Gemara evaluates these requirements and records their evidence. Fullsend and
repository owners supply the evidence and approve promotion. Keeping a result
Unknown is the correct outcome until those claims can be supported.

## Read these three files

1. [Control catalog](../../../experiments/autonomy-platform/policies/controls.json):
   what readiness and candidate requirements exist.
2. [Common policy](../../../experiments/autonomy-platform/policies/common-policy.json):
   which catalog applies and how each requirement is evaluated.
3. [Repository policy](../../../experiments/autonomy-platform/policies/repository-policy.json):
   imports the common policy and adds a documentation-only assessment plan.

These are official-schema Gemara documents. `sdk/policy.go` resolves them and
binds named methods to actual checks. `sdk/main.go` runs the native SDK assessments
and records evidence. Policies are configuration; checking GitHub/Fullsend facts
still requires executable integration code. There is no Gemara server to call.

The repository's documentation restriction produces a second assessment of the
change-class requirement. A dependency-digest fixture passes the common plan and
fails the repository plan; the native aggregate holds. A looser child risk plan
cannot make a failed common risk assessment disappear.

## Replay without a PR

Follow [setup](../../../experiments/autonomy-platform/README.md#run), then:

```sh
python3 experiments/autonomy-platform/demo.py
```

The output labels evidence as synthetic. Complete inputs produce `would_allow`;
failed CI, missing/stale/wrong-revision Review and the repository restriction hold.
Every output forbids mutation. `--write-report` retains native EvaluationLogs in
ignored `out/`, with requirement, policy and plan references.

## Use a real PR

- [PR #28](https://github.com/fullsend-ai/auto-merge/pull/28) has successful CI and
  [an exact-revision Fullsend approval](https://github.com/fullsend-ai/auto-merge/actions/runs/38667018391).
- [PR #29](https://github.com/fullsend-ai/auto-merge/pull/29) intentionally violates
  the example validator and has failed CI. Neither PR is intended to merge.

```sh
python3 experiments/autonomy-platform/github_observe.py --pr 28
python3 experiments/autonomy-platform/github_observe.py --pr 29
```

Each local report contains native readiness/candidate EvaluationLogs and a shadow
decision. CI, Review and findings can pass while risk and readiness remain Unknown.
That holds the overall decision; a green workflow is not permission to merge.
Run `Autonomy shadow observation` on main with either PR number
and read its Summary. The native policy/plan column explains each assessment.

Historical comparison runs: [#28](https://github.com/fullsend-ai/auto-merge/actions/runs/38667624427)
and [#29](https://github.com/fullsend-ai/auto-merge/actions/runs/38667019263).
They verified live collection and conservative holds before the native-policy rewrite.
The reference engine has since been removed.

## What is still missing

This is a Gemara-native implementation for the configured trial. It is not a
universal Policy interpreter. The [runbook](../../../experiments/autonomy-platform/README.md#supported-policy-semantics)
lists unsupported features, all of which fail closed. Official schema validity
alone does not prove that an evaluator supports every declared policy feature.

The next platform questions are a deployed revision-bound risk producer, stronger
finding provenance for production,
independently produced readiness/promotion attestations, and the supported
execution/distribution contract for this evaluator. The local unsigned receipts
and synthetic evidence do not answer them or establish an organizational standard.

Only Fullsend Review is active. No model agent writes merge decisions. The observer
checks out trusted main only and has read-only permissions. No PR code, API body,
review text, credentials or raw workflow logs are retained in its reports.
