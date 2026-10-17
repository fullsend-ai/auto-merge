# Hosted Review with actual Fullsend vendored mode

Status: deployed and exercised on GitHub; the HTTP 401 authentication failure
is fixed, as are the App-set, profile and shell-example startup issues. Hosted
Review currently lacks a usable readonly GitHub credential in the sandbox. Native publication and authenticated artifact consumption are
**not yet proven on a hosted successful Review**. No synthetic replay is called
hosted proof.

## Observed hosted result — 2026-10-16

- Owner-authorized bootstrap deployed commit
  `276ed5d011e4d84e7af4f9e0737036bd64255cd2` directly after ordinary CI and
  Gemara integration tests passed. This was an owner deployment, not a Gemara
  authorized automatic merge. Main's original rules were immediately restored;
  final verification found active enforcement and no bypass actors.
- Documentation [PR #43](https://github.com/fullsend-ai/auto-merge/pull/43), head
  `46262744eded4e75c7a5d57ab6314d41ac5b7f57`, automatically started
  [Fullsend run 38945541104, attempt 1](https://github.com/fullsend-ai/auto-merge/actions/runs/38945541104).
  No `/fs-review` command or manual queue retry was used.
- GitHub reports the local reusable dispatcher at the deployed configuration
  commit. Dispatcher installation using vendored defaults succeeded; upstream
  CLI installation and the Review job's upstream defaults checkout were skipped.
- The Review job failed at **Mint review token**. The mint request returned
  HTTP 401 on all six attempts. Agent execution never started. The retention
  step completed without a file; GitHub lists **zero artifacts** for this run.
- The real read-only observer returned stable observation, candidate **hold**,
  repository readiness **hold**, and native reason
  `native_latest_run_not_successful`. No native Review values were accepted and
  no merge was authorized.

The pinned Fullsend mint source validates the reusable workflow host against
its allowed workflow hosts (`internal/mintcore/claims.go:145` and
`internal/mintcore/oidc_verify.go:57`). Moving from an upstream reusable workflow
to this repository changes that identity. A missing workflow-host enrollment is
a plausible explanation for HTTP 401, **not a confirmed server diagnosis**:
this experiment did not read deployed mint configuration or server logs.

### Repository-only authentication correction (deployed at `597c4b3`)

Instead of changing shared mint enrollment, the shim delegates execution to the official upstream `reusable-dispatch.yml`, pinned to
`1528aac1b8361ef7f5cad1ba55f304402761580c`. That wrapper checks out this repository's
trusted base configuration and uses the committed `.defaults/` action and
vendored binary. Its upstream dispatcher identity uses the previously working platform trust
path. This is a hybrid: vendored runtime with an upstream authentication wrapper,
not a wholly self-contained workflow installation.

The dedicated bounded artifact upload moves into the local composite action, so
it runs inside that wrapper after Review. The consumer requires exactly the upstream dispatcher at the pinned source
revision, while host blob verification binds the local configuration revision. Extra, missing or repinned workflow references fail
closed. No new secrets, token proxy, App permissions or cloud changes are needed.

[Run 38962317342](https://github.com/fullsend-ai/auto-merge/actions/runs/38962317342),
triggered automatically by PR #43 head `dce357e`, verified successful Review token
minting, GCP authentication and vendored binary selection. Agent startup then
failed because the pinned agent harness requires `FULLSEND_APP_SET`, which the
pinned runtime does not export. No native artifact was produced.

The next prepared correction sets the non-secret existing official App prefix
`fullsend-ai` explicitly in `env.runner` in the repository's Review harness. The
post-script already recognizes that prefix, so this adds no new trusted App.
The host lock is refreshed. Deployment of that correction is pending; native
hosted publication and consumption remain unproven. No upstream or shared
infrastructure changes were made.

## Installation and scope

This repo uses the official `CollectVendoredAssets` and
`CollectPerRepoInstallFiles(vendored=true)` implementations from pinned Fullsend
source, rendered offline by `vendor_fullsend_review.py`. It installs:

- the local reusable workflows and `.defaults/` composite actions/defaults;
- a local-dispatch shim and `.fullsend/vendor-manifest.yaml`;
- the built `.fullsend/bin/fullsend` binary, source/build identity and a lock of
  the trusted host blobs.

Unlike the earlier local-only experiment, these assets are committed and the
hosted Review action selects the vendored binary. No Fullsend, Agents, cloud or
organization repository/configuration is modified. Review still uses the pinned
official agent harness, with this lab’s host publication extension.

The ordinary binary is built from a pinned source archive plus the repository’s
native Review evidence command. Binary/source caches remain ignored; only the
28 MB Linux binary and official vendored runtime assets are published. Build
children receive no forge/model/signing credentials. The committed binary’s
hash is recorded and checked by the host publisher.

## Real producer and consumer

After the official post-script successfully posts a review for the exact head,
the trusted host passes its validated final findings projection and selected risk
fields to the native evidence command. Repository/run/configuration identities
come from the runner and authenticated forge metadata, not model text. The native
child receives no credentials. Only the bounded native JSON is uploaded, under
`fullsend-review-evidence-<attempt>`, for 14 days.

The observer uses authenticated Actions metadata to find the artifact, checks
archive integrity and its single bounded JSON member, and verifies the successful
run, attempt, GitHub subject association, local reusable workflow reference and
pinned source blobs. It refuses in-progress/failed newer runs and unsupported
redirects. The API token is never forwarded to the signed Azure blob URL.

Gemara consumes the verified record for AM-REVIEW, AM-FINDINGS and AM-RISK. A
missing/invalid native record does not fall back to legacy comment risk markers
when the vendored host lock is installed. Native producer references/digests are
retained with the evaluation bundle. Native evidence does not bypass readiness,
policy, scope, exact-head authorization or GitHub protections.

## Hosted test and proof to record

Create a harmless new documentation PR outside the automatic pilot’s single
allowed path. Ordinary CI and the actual Fullsend Review should run; the policy
must not merge this out-of-scope PR. Record the review run and attempt, subject
head/configuration, vendored-install step, artifact identity/digest and the
consumer’s authenticated contract/Gemara result. Keep failures visible and fix
only within this repository.

The pre-test local suite passes 107 tests, including native producer/consumer,
artifact-tampering, redirect/token isolation and host-publication projection
checks. Vendored upstream workflow lint requires excluding two inherited warnings:
old actionlint does not recognize GitHub’s `job.workflow_sha/workflow_repository`
fields, and upstream shellcheck SC2016 annotations. Our changed workflow additions
are linted as well. This is not a new upstream security certification.

## Reproduce or retire

Rebuild the pinned binary using `build_fullsend_evidence_lab.py`, render the
vendored assets with `vendor_fullsend_review.py`, then refresh the host lock with
`vendor_fullsend_review.py --lock` after intentional host-source changes. Scan the
published file set and verify lock integrity before deployment. The lock is a
repository trust pin, not a signature or a centrally approved company standard.

Returning to the previous layered installation requires restoring the shim,
removing manifest-listed vendored assets/binary, and restoring a post-script that
does not require native publication. Never leave a missing native publisher with
an apparently passing native-evidence check.

## Provider-profile compatibility correction (prepared, not deployed)

The App-set correction deployed at `6de2c90`. Automatic run
[38963493603](https://github.com/fullsend-ai/auto-merge/actions/runs/38963493603)
passed authentication and environment validation, then failed creating
`github-ro` and `vertex-ai`: their profile types were not imported. The older
pinned agent harness names those providers without declaring profiles; this
pinned runtime imports only explicitly declared profiles. The official
workspace-preparation action intentionally excludes bulk profile copying.

The prepared child harness explicitly declares just `fullsend-github-ro` and
`fullsend-vertex-ai`, using official profile URLs at the binary's immutable
Fullsend source revision and SHA-256 integrity hashes. The GitHub profile enforces
read-only API access. No GitHub write provider, credential or App scope is added.
The actual pinned Fullsend composer, environment validator and profile resolver
have successfully checked this child harness and fetched/verified both profiles
without credentials. A fresh hosted run is still required after deployment.

## Shell skill compatibility correction (prepared, not deployed)

The profile correction deployed at `418d762`. Automatic
[run 38964676701](https://github.com/fullsend-ai/auto-merge/actions/runs/38964676701),
PR head `a51d79d`, started the real agent. Attempts 1 and 2 both returned
`failure / tool-failure`. Failed tool messages show Tirith rejecting the pinned
GitHub Review skill's command-substitution script; a subsequent diagnostic curl
was blocked by DNS/SSRF protection. The native publisher refused the failure
ledger, emitted no record, and the job failed. This is not a completed Review or
an authenticated native evidence proof. Ordinary `fullsend-review` artifacts
exist; those must not be confused with native evidence.

The prepared local skill override retains the pinned official Review guidance
and changes only three Bash examples to file-mediated forms. All nine Bash
blocks pass the checksum-verified sandbox Tirith 0.4.1 binary without guard or
policy changes. Fixture tests verify paginated file collection, malformed commit
counts, the 250-commit cap, unavailable commit data, the 300-file comparison cap
and full-diff fallback. The actual pinned Fullsend composer verifies that this
local GitHub skill replaces the inherited GitHub Review skill; environment and
SHA-pinned profile validation still pass. Provenance and the original skill's
content hash are retained in the override; its blob is included in the host lock.
Deployment and another hosted proof remain pending owner approval.

## Readonly gateway credential correction (prepared, not deployed)

The skill correction deployed at `de797b2`. Automatic
[run 38969764900](https://github.com/fullsend-ai/auto-merge/actions/runs/38969764900),
PR head `47e01bb`, passed the previous startup and initial shell-example checks.
The first GitHub API call failed because no GH_TOKEN was exported. An agent
attempt to use the empty `_NOOP_GITHUB_RO` provider placeholder returned HTTP 401;
that placeholder is not a real credential. The final action was again
`failure / tool-failure`, and no native evidence record was accepted.

The prepared provider mapping replaces the empty placeholder with the reference
`GH_TOKEN: "${GH_TOKEN}"`. The real runtime-minted installation token is delivered
to the gateway through the host process environment; OpenShell exposes a
placeholder in the sandbox. The harness explicitly sets `runtime: read` and
host-side `pre_script`/`post_script: write` under `privilege_levels`. The pinned
runtime mints the runtime token before provider expansion and remints the
post-script token after sandbox teardown. No personal token, stored token value,
new App scope or GitHub write provider is added. The existing enforced readonly
GitHub profile remains unchanged.

Actual Fullsend composition/provider parsing verifies those privilege levels,
the single GH_TOKEN reference, the selected skill override and both pinned
profiles. The vendor renderer reproduces the mapping and the host lock binds it.
Hosted authentication/publication remains unproven until deployment and retest.

### Comparison with current upstream

Read-only inspection on 2026-10-16 confirms that current Fullsend
[`07bb0ea`](https://github.com/fullsend-ai/fullsend/blob/07bb0ea2898cf1a65ac483a43269e60bdf9d6143/internal/scaffold/fullsend-repo/providers/github-ro.yaml)
uses the same `GH_TOKEN: "${GH_TOKEN}"` provider mapping. Its
[stage privilege implementation](https://github.com/fullsend-ai/fullsend/blob/07bb0ea2898cf1a65ac483a43269e60bdf9d6143/internal/harness/privilege.go)
still supports the explicit runtime/read and host-script/write configuration.
The current Agents
[Review harness](https://github.com/fullsend-ai/agents/blob/65c52d7ed90b6f6471d4b5a3e60b818361a32ad4/harness/review.yaml)
still selects the `github-ro` provider. This fix adopts that existing credential
mechanism without updating our binary, agent, image, wrapper or profile pins.
The native evidence publisher remains a repository-local experimental extension;
this comparison does not establish it as a shipped upstream feature.
