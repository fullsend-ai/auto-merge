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

### Current state after cleanup and owner-directed simplification

Immediately after the trial, the original protections were restored. The owner
subsequently requested removing those experimental protections to allow direct
pushes to main. The `merge queue proof` ruleset was deleted; readback confirmed
zero rulesets and no classic main-branch protection. This later change does not
alter the evidence of the protected merge above.

The one-shot grant remains disabled. The workflows and native policies remain in
place; ordinary PR CI still runs, but it is no longer enforced by branch rules.
A future protected-queue pilot must explicitly reinstall its required gate and
protection profile and authorize a fresh grant. The live controller checks that
profile and holds when it is missing. Direct-main writes are development actions,
not evidence of a policy-governed merge.

## What this example actually did

Fullsend Review supplied judgment about a documentation PR. Our collector read
GitHub CI, exact-head review/findings/risk evidence and repository state. Our Go
integration bound those observations to named Gemara assessment methods; native
Gemara evaluated the imported common and repository policies and produced an
EvaluationLog. A separate trusted controller requested queue entry. At the queue
commit, the required gate repeated policy evaluation against the cumulative tree.
GitHub performed the merge only after that gate and ordinary CI passed.

The custom auto-merge model agent was not part of this decision. Gemara did not
review code, run CI, fetch GitHub evidence by itself, or merge the PR. The lab's
collector, assessment implementations and controller supplied those integrations.

### What starts shadow observation?

[autonomy-shadow.yml](../../../.github/workflows/autonomy-shadow.yml) has two triggers:

- Manual `workflow_dispatch` with a PR number; optional `verify_example` also
  checks the positive/negative shadow fixtures and readiness holds.
- `workflow_run` after either workflow named `CI` or `fullsend` completes,
  regardless of success or failure. Its job runs only in this repository on main
  and only when the triggering run contains a PR number. Otherwise the workflow
  can appear as skipped. It currently selects the first linked PR.

Both paths check out trusted main code, collect read-only metadata and emit a
normalized policy summary. They cannot merge or change repository settings.
`fullsend` runs triggered by issue comments may lack a linked PR in their run
metadata; manual dispatch is the fallback. There is no polling schedule and no
custom model agent in this observer.

### What is portable, and what overlaps with GitHub?

Checking CI, approvals, unresolved discussions and revision identity overlaps with
native forge capabilities. Here those observations also feed a common policy and
structured evidence record. The extra Fullsend-specific checks include matching
review findings and risk receipts to the exact revision, restricting allowed
change classes and governed paths, and evaluating repository readiness.

The reusable design is a common Gemara catalog/policy and evaluation contract,
with forge-specific evidence collection and enforcement. The current lab is
GitHub-specific; a GitLab collector/controller has not been implemented or tested.
Policies alone cannot turn GitHub API fields into GitLab evidence. Nor do policies
prevent an unrelated writer from merging unless the forge or another authoritative
control enforces the decision. Native branch rules can also be provisioned through
APIs with owner authorization; Gemara complements that enforcement.

See [Gemara's integration FAQ](https://gemara.openssf.org/faq/) for the distinction
between reusable artifacts and evaluation-tool integration.
