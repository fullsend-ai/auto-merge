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

During the experiment, the rules require **Gemara pilot queue gate**, bound to the
GitHub Actions producer, as well as the existing three checks. The queue builds
and merges one entry at a time. A current approval, stale-review dismissal and
conversation resolution are also required.

[The queue workflow](../../../.github/workflows/autonomy-queue.yml) loads code from
the platform-supplied trusted main base. It waits for the ordinary CI checks on
the actual cumulative group SHA, rechecks Fullsend/candidate evidence and evaluates
the lab policy against that group SHA. It also verifies:

- the group identifies exactly the granted PR and head;
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
