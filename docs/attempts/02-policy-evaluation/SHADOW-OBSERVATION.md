# Follow native Fullsend Review evidence into Gemara

See [current state](CURRENT-STATE.md) for the complete proof map. Shadow evaluation
is read-only. It keeps candidate eligibility, repository readiness and action
authorization separate; a successful observation job can still report **hold**.

## The current hosted example

[PR #43](https://github.com/fullsend-ai/auto-merge/pull/43), head
`d7383caff19e3b8e69eb76e72f7b99e99faf30c0`, automatically ran
[Fullsend Review 38993688485](https://github.com/fullsend-ai/auto-merge/actions/runs/38993688485)
using the committed vendored binary under the pinned upstream authentication
wrapper. The trusted host published `fullsend-review-evidence-1` (artifact
`12086559170`). No manual review command or queue retry was used.

The [automatic Gemara shadow run 38995415634](https://github.com/fullsend-ai/auto-merge/actions/runs/38995415634)
retained bundle `12086967236`. Open its files in this order:

1. `review-evidence-reference.json`: `contract_verified`, producer run/attempt,
   artifact ID, payload digest and exact subject.
2. `candidate-evaluation-log.json`: native control/requirement/policy-plan results.
3. `decision.json`: hold, separate production readiness, subject and reasons.
4. `effective-policy.json`: the actual loaded policy/catalog documents.
5. `normalized-evidence.json`, `manifest.json` and `summary.md`: bounded inputs,
   integrity digests and readable explanation. The manifest is not a signature.

Fullsend's native record says approve, risk 1 (low), with one open low-severity
missing-doc finding. AM-REVIEW and AM-RISK passed. AM-FINDINGS failed and AM-CLASS
was unknown. The overall decision and repository readiness remained hold.
Our policy conservatively holds on any open finding; model approval cannot erase it.

## Which code does what

- The host publisher finalizes a bounded findings/risk record from validated
  host-owned state. Model prose and self-claimed trust are not accepted as proof.
- `native_review_artifacts.py` verifies authenticated GitHub run/artifact metadata,
  exact repository/head/base/configuration, run attempt, expected wrapper and host
  sources, archive integrity and freshness. It selects automatic Review runs;
  missing native evidence holds when the vendored lock is installed.
- The observer supplies normalized observations to the native Gemara evaluator.
  Gemara policies reference named methods; the integration implements collection
  and method execution. It does not interpret arbitrary prose as executable checks.
- Readiness is assessed separately. Missing assurance remains unknown; the
  observer grants no merge authority. The [pilot](DOCUMENTATION-AUTO-MERGE-PILOT.md)
  has a distinct owner-enabled authorization and scoped writer.

## Read the policy before the implementation

- [Control catalog](../../../gemara-auto-merge/catalogs/repository-readiness-and-pr-controls.json): requirements for readiness and PR candidates.
- [Common policy](../../../gemara-auto-merge/policies/common-auto-merge-policy.json): assessment plans, including risk limit.
- [Repository policy](../../../gemara-auto-merge/policies/repository-auto-merge-policy.json): additional restrictions, not permission to remove common requirements.

The [implementation runbook](../../../gemara-auto-merge/README.md#supported-policy-semantics)
names the supported subset and unknown/unsupported behavior. Policies are draft lab
artifacts, not an approved Red Hat standard.

## Reproduce safely

After [pinned local setup](../../../gemara-auto-merge/README.md#run):

```sh
python3 -m unittest discover -s gemara-auto-merge -p 'test_*.py'
python3 gemara-auto-merge/run_review_evidence_examples.py
python3 gemara-auto-merge/github_pr_evidence.py --pr 43
```

The 15 producer replays use synthetic inputs and publication proof, with no merge
authority. The real observer reads current state: old evidence is not made fresh
by downloading it. Its 600-second limit means a later observation may correctly
hold on freshness or changed context rather than reproduce the historical result.
Use the retained hosted bundle to teach the original evaluation. Workflow artifacts
have finite retention; exact expiry is recorded in [current state](CURRENT-STATE.md).

## Historical examples

The earlier [positive #28](https://github.com/fullsend-ai/auto-merge/pull/28) and
[negative #29](https://github.com/fullsend-ai/auto-merge/pull/29) demonstrated the
receipt-based shadow path in [run 38739054288](https://github.com/fullsend-ai/auto-merge/actions/runs/38739054288).
The old recorded-trial verifier checks that earlier scenario and is not the current
native-artifact smoke test. Do not present its old revisions as freshly eligible.
[PR #41](https://github.com/fullsend-ai/auto-merge/pull/41) separately demonstrated
a protected merge through the earlier route. Native publication does not yet have
a successful full-path merge proof. See the [hosted chronology](HOSTED-VENDORED-REVIEW.md)
for intermediate failures and the final native producer/consumer success.
