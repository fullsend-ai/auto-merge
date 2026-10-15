# Follow the native Gemara trial

The evaluator now uses one engine and native Gemara artifacts. The previous
hosted comparison runs are historical evidence, not proof that this new version
has been deployed. The new native path is tested locally against these same public PRs and prepared
for the trusted-main workflows. The credential-free local observations returned
no API errors: #28 passed CI and exact-revision Review, #29 failed CI, and both
held on missing evidence. Each native output passed official schema validation.

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
decision. CI and Review can pass while findings, risk and readiness remain Unknown.
That holds the overall decision; a green workflow is not permission to merge.
After publication, run `Autonomy shadow observation` on main with either PR number
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

The next platform questions are trusted revision-bound findings/risk evidence,
independently produced readiness/promotion attestations, and the supported
execution/distribution contract for this evaluator. The local unsigned receipts
and synthetic evidence do not answer them or establish an organizational standard.

Only Fullsend Review is active. No model agent writes merge decisions. The observer
checks out trusted main only and has read-only permissions. No PR code, API body,
review text, credentials or raw workflow logs are retained in its reports.
