# Repeatable Gemara auto-merge pilot

This is a bounded public-repository experiment with an explicit owner-enabled lab
policy. It is not an approved organizational auto-merge standard or production
qualification. The custom auto-merge model agent remains disabled.

## Draft configuration, not deployed

[pilot-config.json](../../../experiments/autonomy-platform/policies/pilot-config.json)
is the proposed repository-owned configuration on PR #32. It defines two paths;
neither is deployed by this draft. Current main still uses the disabled, spent
one-PR grant from the earlier experiment:

- **Automatic documentation pilot:** one ordinary modified file,
  `docs/example-feature.md`, with at most 20 changed lines. The unchanged native
  common/repository candidate policies must pass: current Fullsend approval,
  verified findings/risk, CI, allowed change class and governed-path restrictions.
- **Maintainer maintenance:** an admin or maintainer explicitly dispatches the
  pilot for an exact PR/head with `maintenance=true`. This is a human-authorized
  path, not automatic promotion of a failed candidate. It covers bounded regular
  file changes in the lab's workflow, harness, policy, code and documentation paths.
  Its separate native policy still requires CI, integration tests, trusted source,
  exact queue tree, protections and clear discussions.

`automatic_enabled=false` stops automatic entry and authorization. Maintenance is
independently controlled so a maintainer can make a governed policy/configuration
change while automatic merging is disabled. No PR can enable its own policy:
all decisions load configuration and evaluator code from current main.

## Workflow path

[Gemara live merge pilot](../../../.github/workflows/autonomy-pilot.yml) listens
for completed `CI` and `fullsend` runs, and supports manual dispatch. A read-only
resolver binds one current same-repository PR to its exact current head. For
Fullsend slash-command runs without linked PR metadata, it can use a matching
pinned-producer risk receipt as a routing hint. The evaluator independently verifies
that evidence; the hint grants no authority. Merge-group CI cannot retrigger entry.

A read-only job evaluates native Gemara policy. Only if eligible does a separate
writer repeat the evaluation and request GitHub's protected queue with
`--auto --match-head-commit`. There is no admin merge in the live path.

[Gemara merge queue validation](../../../.github/workflows/autonomy-queue.yml)
waits for ordinary CI on GitHub's actual cumulative commit, re-evaluates policy,
and verifies the queued tree against the reviewed head and current base. The
reviewed file blobs must match; unrelated changes, symlinks, missing evidence,
changed configuration or unknown revision state hold. The queue builds and merges
one entry at a time. GitHub performs the merge after required checks pass.

The PR-stage queue check only defers final validation. It does not approve entry.
The required check context is **Gemara pilot queue gate**, bound to GitHub Actions,
in addition to the three original required CI contexts. Conversation resolution,
stale-review dismissal, deletion protection and non-fast-forward protection remain
required; there are no bypass actors in the steady-state ruleset.

## Repository-only App-token handoff: blocked

The writer is a local reusable workflow in this repository. It uses the existing
published Fullsend mint action; it does not depend on an unmerged workflow in
another repository. Two repo-hosted read-only probes returned HTTP 401. No token
was obtained and no queue request was made in those probes.

The deployed mint does not currently authorize this repository-hosted writer.
This remains a blocker for the App-token handoff. No PAT fallback, new secret,
external trust change or upstream repository change is authorized by this spike.
The implementation stays draft until a repository-only supported path is validated.
An earlier external prototype is not part of this repository-only design or proof.

If the writer can obtain an authorized installation token in the future, it must
verify the token selects only this repo, use it only inside the job for exact-head
queue entry, and revoke it. The collector and native evaluator do not receive it.
Read-only probes check out an immutable reviewed adapter, not caller-branch code.

## Exact-head maintenance authorization

Only manual `workflow_dispatch` may authorize maintenance. Its trusted workflow
run title binds the PR and full head SHA. Both original and rerun actors must still
have repository admin or maintain permission. The source SHA must equal current
main. The run must be no older than one hour. Recent dispatches are searched through
the age boundary with bounded pagination. The authorizing evaluation must have
completed successfully; its separate writer may still be finishing queue entry.

The queue gate looks up a matching dispatch with a successful evaluation job, checks those properties
again and evaluates the separate
[maintenance policy](../../../experiments/autonomy-platform/policies/maintenance-policy.json).
Changing the head, advancing main, expiring the authorization or removing the
actor's permission invalidates it. Automatic event resolution cannot create this
authorization. The original PR #30 grant is archived as
[historical evidence](history/pr30-grant.json), not used for future decisions.

## What production readiness hold means

Our prototype collector deliberately leaves four general assurance inputs unknown:

- Test sufficiency: the toy validator is not accepted testing-quality assurance.
- Runtime isolation: the deployed Review runtime has not been attested here.
- Trusted publication: no general production eligibility-publisher approval exists.
- Shadow history: accepted outcomes and promotion criteria are not implemented.

Gemara applies our draft policy to those unknowns; it has not independently
investigated them or certified the repository. The bounded automatic lab pilot is
an explicit owner-enabled exception to production qualification. Maintenance is
an explicitly human-authorized operation. Neither silently marks readiness green.

## Evidence

The original [PR #30](https://github.com/fullsend-ai/auto-merge/pull/30) merged at
`58e7440e420c9c62094f77c35ebb71e6a833b6f7` after
[ordinary group CI](https://github.com/fullsend-ai/auto-merge/actions/runs/38762151272)
and the [required native gate](https://github.com/fullsend-ai/auto-merge/actions/runs/38762151257)
passed. That trial needed an operator queue retry because its Actions-token entry
started no queue workflows. It is historical evidence, not the new App-token proof.

Current implementation validation and live positive/negative results are recorded
in [WORKLOG.md](WORKLOG.md). The App-token handoff remains blocked; no new live merge outcome is claimed. Historical disabled workflow runs are retained.
