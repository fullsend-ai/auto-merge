# Repeatable Gemara auto-merge pilot

Start with [current state and separate hosted proofs](CURRENT-STATE.md). The
#41 merge used the earlier receipt route; the newest #43 native-artifact trial
verified publication/consumption and held. A successful merge through the newest
route has not yet been demonstrated.

This is a bounded public-repository experiment with an explicit owner-enabled lab
policy. It is not an approved organizational auto-merge standard or production
qualification. The custom auto-merge model agent remains disabled.

## Bounded pilot configuration

[documentation-auto-merge-settings.json](../../../gemara-auto-merge/config/documentation-auto-merge-settings.json)
is the repository-owned configuration introduced by PR #32. The owner-authorized
bootstrap replaces the disabled spent one-PR grant. Installation and hosted
outcomes must be recorded separately:

- **Automatic documentation pilot:** one ordinary modified file,
  `docs/example-feature.md`, with at most 20 changed lines. The unchanged native
  common/repository candidate policies must pass: current Fullsend approval,
  verified findings/risk, CI, allowed change class and governed-path restrictions.
- **Maintenance is disabled for this demo.** The retained experimental path is
  limited to documentation, requires an explicit execute dispatch and an
  independent current-head approval by an admin or maintainer who authored
  neither the PR nor its commits. Queue authorization also requires a successful
  evaluation and writer job from the same exact run attempt. It is not a route
  for workflow, evaluator, policy, configuration or harness changes; hosted
  entry-mode binding remains a prerequisite for any future maintenance rollout.

Automatic authorization expires at `2026-10-22T18:00:00Z` (October 22, 2026,
2 p.m. EDT). An expired or disabled cohort produces a native `LP-AUTH` hold.
`automatic_enabled=false` stops automatic entry and authorization.

Evaluator code and configuration are loaded from current main. Workflow YAML for
merge groups can include PR changes, so that checkout alone does not protect the
required check. The deployment also requires GitHub code-owner review for governed
paths. CODEOWNERS covers workflows, the harness, evaluator/policies, scripts,
security contract and repository instructions. Those paths are excluded from the
automatic documentation cohort and the retained maintenance path. Their changes
need human governance rather than authorization by the PR's own modified gate.

## Workflow path

[Gemara live merge pilot](../../../.github/workflows/gemara-auto-merge.yml) listens
for completed `CI` and `fullsend` runs, and supports manual dispatch. A read-only
resolver binds one current same-repository PR to its exact current head. For
Fullsend slash-command runs without linked PR metadata, it can use a matching
pinned-producer risk receipt as a routing hint. The evaluator independently verifies
that evidence; the hint grants no authority. Merge-group CI cannot retrigger entry.

With the vendored host lock installed, the active verifier requires a native
Review artifact from an automatic `pull_request_target` run. It checks exact
repository, PR, head/base/configuration, producer run/attempt, successful completion,
expected wrapper, host/source pins, archive integrity and freshness. GitHub-owned
check-suite context must unambiguously bind the PR/head/base; a record's own
configuration claim is not proof. Missing or invalid publication holds, with no
silent fallback to the older risk marker.

The native evidence age cap is 600 seconds. Changed revision/configuration,
ambiguous provenance, a newer failed/in-progress run or stale evidence holds.
The hosted trial proves publication and independent shadow consumption, not a
completed native-path queue/merge. The existing writer and queue evaluator consume
the same observer; a fresh eligible end-to-end native trial remains required.

The earlier receipt verifier supports automatic and `/fs-review` paths; it remains
historical code when the native lock is installed. Do not infer native command-run
support from that older verifier. A command cannot waive the current contract.
See [the Review contract](REVIEW-EVIDENCE-CONTRACT.md) for the active trust boundary.

A read-only job evaluates native Gemara policy. Only if eligible does a separate
writer repeat the evaluation and request GitHub's protected queue with
`--auto --match-head-commit`. There is no admin merge in the live path.

[Gemara merge queue validation](../../../.github/workflows/gemara-merge-queue.yml)
waits for ordinary CI on GitHub's actual cumulative commit, re-evaluates policy,
and verifies the queued tree against the reviewed head and current base. The
reviewed file blobs must match; unrelated changes, symlinks, missing evidence,
changed configuration or unknown revision state hold. The queue builds and merges
one entry at a time. GitHub performs the merge after required checks pass.

The PR-stage queue check only defers final validation. It does not approve entry.
The required check context is **Gemara pilot queue gate**, bound to GitHub Actions,
in addition to the three original required CI contexts. Conversation resolution,
stale-review dismissal, code-owner review, deletion protection and non-fast-forward protection remain
required; there are no bypass actors in the steady-state ruleset.

## Temporary repository App handoff

The writer is configured to use the dedicated private lab GitHub App
`gemara-auto-merge-pilot-lab` (App ID `5334789`, installation `171824120`).
Its only installation selects only `fullsend-ai/auto-merge`. Registration,
installation and a metadata-only installation-token scope check were verified
on October 15, 2026. The probe token was revoked. The key is stored only as an
encrypted environment secret; the temporary local key copy was removed.
PR #32 installs this workflow through the documented owner bootstrap. This is a
temporary credential mechanism, not the
Fullsend-native token handoff. Two earlier repository-hosted Fullsend mint probes
returned HTTP 401; that integration remains unresolved. An external prototype
is excluded from this repository-only design and proof.

The reviewed [App manifest](../../../gemara-auto-merge/config/temporary-merge-writer-app-manifest.json)
requests Contents and Pull requests write permissions, no organization or
administration permissions, no webhook events and no user authorization. The App
must not appear in any ruleset bypass list. Its only installation must select
this repository, not all repositories.

The `gemara-pilot-writer` Actions environment allows branch `main` only. It holds
`GEMARA_PILOT_APP_PRIVATE_KEY` as an encrypted environment secret and
`GEMARA_PILOT_APP_ID` as a non-secret environment variable. The private key is
long-lived; protecting it remains necessary even though installation tokens expire.
It must never be committed, logged, passed to PR code, model agents, builds or tests,
or included in artifacts. No personal token or Fullsend App key is copied to Actions.

The writer executes trusted main code and prepares the evaluator before minting.
It uses the [official GitHub token action](https://github.com/actions/create-github-app-token)
at a pinned commit, requests only this repository and the required permissions,
and leaves default post-job revocation enabled. A manual read-only probe on main
requests read permissions and verifies scope without queue entry. An executing
writer verifies the single-repository token scope again, repeats native policy
evaluation and requests only the exact reviewed head through GitHub's protected queue.

Registration, installation, hosted token verification and repeatable live trials
must each be recorded separately; changing the writer does not prove those steps
have succeeded. Do not claim hosted queue-entry proof until those run results are recorded.

To retire the workaround: disable automatic pilot entry, remove the environment
secret and variable, uninstall/delete the dedicated App and its private key, and
replace only the credential acquisition step once Fullsend supports this writer.
Keep Gemara policy and all GitHub protections enforced throughout the transition.

## Exact-head maintenance authorization

Only manual `workflow_dispatch` may authorize maintenance. Its trusted workflow
run title binds the PR and full head SHA. Both original and rerun actors must still
have repository admin or maintain permission. The source SHA must equal current
main. An independent current-head human approval is also required; the reviewer
must be a current admin/maintainer and cannot be the PR or a commit author. The run must be no older than one hour. Recent dispatches are searched through
the age boundary with bounded pagination. Both the evaluation and writer job must have completed successfully in the same
run attempt. Evaluate-only dispatches grant no merge authority. Maintenance is
disabled in the shipped pilot configuration; this retained path is not live proof.

The queue gate looks up a matching explicit-execute dispatch with successful evaluation and writer jobs, checks those properties
again and evaluates the separate
[maintenance policy](../../../gemara-auto-merge/policies/maintainer-approved-documentation-policy.json).
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
in [WORKLOG.md](WORKLOG.md). The dedicated lab App handoff was demonstrated by [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41), merged October 16, 2026 at `89f5f2f507d936456439943cb696f45efa07dea1`. The [writer run](https://github.com/fullsend-ai/auto-merge/actions/runs/38900418833) and [required Gemara queue gate](https://github.com/fullsend-ai/auto-merge/actions/runs/38900537957) passed; the lab App queued and merged the PR without a manual review command or queue retry. This proves only the bounded documentation pilot. The Fullsend-native credential handoff remains separate and unresolved. Historical disabled workflow runs are retained.

See [the retained proof](history/pr41-proof.json), [current state](CURRENT-STATE.md)
and [hosted native record](HOSTED-VENDORED-REVIEW.md) for the two distinct proofs.
[D1–D4](D1-D4-REPORT.md) is the earlier local-validation snapshot, not current deployment status.
