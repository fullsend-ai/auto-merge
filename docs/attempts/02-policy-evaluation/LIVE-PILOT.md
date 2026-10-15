# Repeatable Gemara auto-merge pilot

This is a bounded public-repository experiment with an explicit owner-enabled lab
policy. It is not an approved organizational auto-merge standard or production
qualification. The custom auto-merge model agent remains disabled.

## What is enabled

[pilot-config.json](../../../experiments/autonomy-platform/policies/pilot-config.json)
is the repository-owned configuration. It enables two distinct paths:

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

## Fullsend App-token handoff

The lab pins a restricted upstream reusable writer from
[Fullsend draft PR #8467](https://github.com/fullsend-ai/fullsend/pull/8467).
This is an unmerged spike component, not a shipped general Fullsend feature.
It accepts only this repository and named caller. Fullsend's existing OIDC mint
issues a short-lived coder-role installation token scoped to `auto-merge`.
The existing role has a broader permission ceiling than a future dedicated merge
role; this prototype does not add a new role or change mint trust settings.

The App token stays inside the writer job and is used only for installation-scope
verification, the exact-head queue request, and revocation. It is not an output
passed back to the caller, not a PAT, and not supplied to the model or native
assessment subprocesses. The collector uses the standard read-only Actions token.
The job checks out trusted caller-main code, never the PR or synthetic tree.

Two repository-hosted mint probes returned HTTP 401. The upstream-hosted
[read-only probe](https://github.com/fullsend-ai/auto-merge/actions/runs/38775102361)
succeeded, verified the single-repository token scope, then revoked the token.
The selected upstream host is a demonstrated mint boundary, not a Gemara feature.

## Exact-head maintenance authorization

Only manual `workflow_dispatch` may authorize maintenance. Its trusted workflow
run title binds the PR and full head SHA. Both original and rerun actors must still
have repository admin or maintain permission. The source SHA must equal current
main. The run must be no older than one hour.

The queue gate looks up a successful matching dispatch, checks those properties
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
in [WORKLOG.md](WORKLOG.md). The separate shared-component draft remains subject
to upstream review. Historical disabled workflow runs are retained.
