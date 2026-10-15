# Live Gemara-governed merge trial

This extends the [shadow example](LIVE-TRIAL.md) into an owner-authorized activation
of Gemara mode for **one documentation PR and exact head**. The owner explicitly
authorized a live auto-merge experiment in this test repository. Production
readiness remains unqualified; the exception is visible and bounded rather than
marking those assurance controls passed.

## Authorization and policy

[The committed grant](../../../experiments/autonomy-platform/policies/live-pilot-grant.json)
selects one PR/head, an expiration and a maximum changed-line count. Disabled,
expired, malformed or nonmatching grants cannot enqueue. Changing the head requires
a new owner grant. A closed/merged PR cannot reuse the grant.

The original native common/repository candidate policies must still pass. The
additional [native lab catalog](../../../experiments/autonomy-platform/policies/live-pilot-controls.json)
and [native lab policy](../../../experiments/autonomy-platform/policies/live-pilot-policy.json)
require the exact grant, document scope/tree, trusted main sources, passing candidate
assessment, revision-specific CI, protected single-entry queue and clear discussions.
There is still one Gemara evaluator. The lab policy is an explicit scoped exception
to production qualification, not an approved organizational readiness standard.

## The actual controller

[Autonomy live pilot](../../../.github/workflows/autonomy-pilot.yml) is manually
dispatched on main with a PR number and head. `execute=false` evaluates only.
`execute=true` allows a separate write-capable job after the read-only evaluation
succeeds. That writer repeats the full evaluation immediately before invoking:

```sh
gh pr merge NUMBER -R fullsend-ai/auto-merge --auto --match-head-commit HEAD
```

It never uses an admin merge or a direct merge API. GitHub retains its native merge
queue and required checks. No personal token or new secret is stored in Actions.
Only the writer has contents/pull-request write permissions; evaluator children
receive clean environments, and no PR or synthetic-commit code is executed.

## Final authorization on the merge group

During the completed experiment, the rules required **Gemara pilot queue gate**, bound to the
GitHub Actions producer, as well as the existing three checks. The queue built
and merged one entry at a time. Fullsend approval is mandatory in the native candidate policy. Stale-review
dismissal and conversation resolution are also required. The separate GitHub
human-approval count was zero for this owner-authorized experiment.

[The queue workflow](../../../.github/workflows/autonomy-queue.yml) loads code from
the platform-supplied trusted main base. It waits for the ordinary CI checks on
the actual cumulative group SHA, rechecks Fullsend/candidate evidence and evaluates
the lab policy against that group SHA. It also verifies:

- the group ref identifies the granted PR and base, and GitHub queue-entry
  metadata binds the reviewed head, base and actual group commit;
- the queued document is an ordinary file with exactly the reviewed blob;
- every other file/submodule entry equals the current main base;
- the actual target branch, source policy/code and grant remain current;
- the grant is unexpired and no unresolved threads or changes requests remain.

It exits nonzero on missing, changed or failed evidence. GitHub can merge only
after this required group check passes. Its PR-stage success merely defers final
queue validation; it is not an eligibility approval.

This deliberately supports GitHub's observed one-entry `gh-readonly-queue/main/pr-N-SHA`
ref shape. Unknown shapes hold. It is not a general multi-PR batching implementation.

## Trial record and cleanup

The worklog records setup, live run IDs, candidate/queue SHAs, merge outcome and
restoration. The pre-existing negative shadow PR remains unmerged. A separate
nonmatching-grant dispatch verifies that the writer is not reached.

After the live experiment, the one-shot grant is disabled and the original queue
rules are restored. The repository's native auto-merge feature remains enabled;
future Gemara-controlled experiments require another explicit grant and the
required queue protection. Broad autonomous rollout remains a separate decision.

The general GitHub behavior is documented in the
[CLI merge manual](https://cli.github.com/manual/gh_pr_merge) and
[merge-queue configuration guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).


## Observed GitHub approval distinction

Fullsend approved the exact head, and native candidate policy passed. With an
additional GitHub required-review count of one, GitHub nevertheless reported
REVIEW_REQUIRED and held the auto-merge request outside the queue. A Fullsend
approval is not automatically an eligible GitHub required review in this setup.
The experiment therefore uses zero independent human approvals, with Fullsend
approval still enforced by Gemara and the required cumulative queue gate. The
original repository rules had no required-review count. No review-app permissions
or administrative merge bypass were added to work around this distinction.

## Verified result: PR #30 merged

On October 15, 2026 at 15:44:03 UTC,
[PR #30](https://github.com/fullsend-ai/auto-merge/pull/30) merged through the
protected queue. The exact merged and evaluated commit is
`58e7440e420c9c62094f77c35ebb71e6a833b6f7`.

- [Controller evaluation and writer](https://github.com/fullsend-ai/auto-merge/actions/runs/38761451293)
  passed against main `315bb6bc35018c91a5e3c8175fc32bb50c9e5dbd` and reviewed head
  `d1b22cadb90264675b6ca9f7c5aaa9b8fc44cd93`.
- [Ordinary queue CI](https://github.com/fullsend-ai/auto-merge/actions/runs/38762151272)
  passed all three required checks, including the four-minute integration check.
- [Required Gemara queue gate](https://github.com/fullsend-ai/auto-merge/actions/runs/38762151257)
  passed all seven native lab controls against that actual cumulative commit.
  Its independent production-readiness result remained `hold`.
- [Hosted regression fixtures](https://github.com/fullsend-ai/auto-merge/actions/runs/38759337735)
  passed 56 Python tests. The final review-count adjustment also passed all 56 locally.
- [Nonmatching-grant negative run](https://github.com/fullsend-ai/auto-merge/actions/runs/38758510031)
  rejected PR #29 and skipped the writer. That PR remains unmerged.

### Credential handoff found by the trial

The controller's Actions-token request entered the queue, but its first group
`5ca817e71f750657e3e94e96897e06728b214a0a` received no Actions workflow runs.
The operator dequeued it and retried the same exact-head native queue request
from an authorized local CLI. This produced the successful group above and
started both required workflows. There was no admin merge and no check bypass
for the trial PR. This is a verified operator-assisted live merge, not proof
of a fully unattended Actions-token deployment.

[GitHub documents token-trigger restrictions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
The observation is consistent with those restrictions. A hosted Fullsend
integration should use an appropriately scoped GitHub App installation token for
queue entry, and repeat this test with that identity. We did not add a PAT, App
private key, or new secret to this public repository. That hosted credential path
remains untested here; Gemara does not supply forge credentials or dispatch CI.

### Current state after cleanup

The exact-head one-shot grant is disabled. The original merge queue, its three
required CI checks, deletion protection and non-fast-forward protection are
restored with no bypass actors. The temporary fourth required check and extra
review-rule profile were removed with that restoration; the workflows remain as
an inactive example. The native auto-merge repository feature was already enabled
and remains enabled. A future Gemara-controlled trial must explicitly install the
required queue gate/protection profile and authorize a fresh bounded grant first.
