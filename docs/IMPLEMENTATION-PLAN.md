# Auto-Merge lab implementation plan

Status: in progress

This is the living execution record for `ascerra/auto-merge`. Update the status,
evidence links, and discovered constraints after every material phase.

## Success criteria

The exercise is complete only when all of these statements are proven:

- The repository is private and the only project modified by the exercise.
- Fullsend is installed in per-repository mode from a pinned current Fullsend
  main commit.
- Repo-scoped inference trusts only `ascerra/auto-merge`.
- Required Fullsend role apps are installed only for this repository.
- `/fs-triage` on an example issue launches the normal triage path.
- The code agent creates a signed-off pull request implementing the issue.
- Review and fix execute, and the final approval applies to the final head SHA.
- Fast and deliberately delayed four-minute CI checks pass on that head.
- The custom Auto-Merge agent performs deterministic preflight, bounded model
  assessment, write-ahead receipt, and authoritative postflight.
- The post-script either rejects with an auditable reason or merges using an
  expected-head compare-and-swap.
- No credential appears in git history, logs captured in the repository, issue
  text, pull request text, comments, or agent evidence.

## Phase 0 - security and capability gate

- [x] Create `ascerra/auto-merge` as a private repository.
- [x] Confirm CLI GitHub access without printing credentials.
- [x] Build the latest Fullsend main locally for features newer than v0.43.0.
- [x] Preview a repo-scoped Vertex WIF provider in a dedicated
  `ascerra-auto-merge` pool whose condition is exactly
  `assertion.repository == 'ascerra/auto-merge'`.
- [x] Provision and verify that provider.
- [x] Record a secret-name-only inventory after setup.
- [x] Install only the required GitHub role apps for this repository.

The available GCP service account lacks
`iam.workloadIdentityPools.create` and
`iam.workloadIdentityPoolProviders.get`. Fullsend documents
`roles/iam.workloadIdentityPoolAdmin` and
`roles/resourcemanager.projectIamAdmin` as required for provisioning. Two
attempts failed on the first create-pool request with HTTP 403; neither reached
provider creation nor project IAM mutation. The dedicated pool/provider and
repository-scoped IAM member were subsequently created through Adam's
authenticated console session without granting that service account broader
administrative roles.

Isolation decision: use `--pool ascerra-auto-merge`, not Fullsend's shared
`fullsend-inference` default. The public mint uses the separate `fullsend-pool`.
Provisioning may add only the dedicated pool/provider and one additive
`roles/aiplatform.user` project IAM member whose principal is scoped to
`attribute.repository/ascerra/auto-merge`. No mint deploy, enroll, update,
deprovision, disable, or delete command is permitted in this exercise.

Billing decision: Adam explicitly approved `it-gcp-konflux-dev-fullsend` for
the lab's inference usage. Isolation is provided by the dedicated pool/provider
and exact repository condition. The only shared-project IAM mutation is an
additive `roles/aiplatform.user` member scoped to that repository principal;
the public mint's pool, providers, service, secrets, and IAM principals remain
unchanged.

GitHub constraint: private repositories owned by this personal account cannot
enable branch protection without GitHub Pro. GitHub native auto-merge is
disabled and the agent enforces required checks, review freshness, unresolved
threads, and exact-head mutation itself.

## Phase 1 - repository fixture

- [x] Add the normative security contract.
- [x] Add a deterministic documentation validator.
- [x] Add a fast required CI job.
- [x] Add a second CI job with a deliberate 240-second delay.
- [x] Protect workflow, Fullsend, ownership, scripts, and security-contract
  paths through CODEOWNERS.
- [x] Commit with DCO sign-off and push the initial `main` branch.
- [x] Configure conservative merge settings (squash only, delete merged branch,
  native auto-merge disabled).
- [ ] Configure required checks through branch protection (unavailable on this
  private personal-account repository; enforced by the agent instead).

## Phase 2 - Fullsend per-repo installation

- [x] Run `fullsend github setup ascerra/auto-merge` with the exact inference
  project/provider, runtime, current Fullsend ref, and DCO sign-off.
- [x] Review every generated file and GitHub-side variable/secret name.
- [x] Verify the shim reads trusted configuration from the base branch.
- [x] Verify the GitHub-side scaffold, variables, secrets, Actions enablement,
  and custom dispatch independently (`fullsend github status` currently accepts
  organizations only, not per-repo targets).
- [x] Trigger harmless triage and code commands and retain the Actions URLs as
  runtime proof.

## Phase 3 - custom Auto-Merge agent

- [x] Generate `auto-merge` with `fullsend agent new` using the hosted `coder`
  role and `/fs-auto-merge` trigger.
- [x] Replace the generated prompt with the bounded semantic policy.
- [x] Implement a pre-script that fetches fresh PR state and fails closed.
- [x] Define a strict APPROVE/REJECT/ESCALATE result schema.
- [x] Implement write-ahead decision receipts.
- [x] Implement postflight revalidation and exact-head merge mutation.
- [x] Bind privileged postflight independently to immutable runner policy and
  the triggering repository/PR URL; reject model-visible evidence tampering.
- [x] Add fixture-based unit tests covering stale SHA, stale approval, pending or
  failed checks, hold labels, disallowed paths, invalid model output, unknown
  mergeability, receipt mismatch, and successful exact-head merge.
- [x] Run local static validation and custom-command dispatch validation.
- [x] Run a no-mutation dry run against the exercise PR.
- [x] Scan tracked content for secret-like material before commit.

Lab limitation: the hosted mint exposes existing roles rather than a distinct
`auto-merge` role, so this experiment uses `coder`. The production design must
give the post-script a purpose-built least-privilege identity and keep that
credential unavailable to the model sandbox.

## Phase 4 - end-to-end exercise

- [x] Create an issue requesting a small update to `docs/example-feature.md`
  with the contract in `AGENTS.md` as acceptance criteria.
- [x] Comment `/fs-triage` and capture the triage run URL/result.
- [ ] Confirm the code agent creates a PR and all commits pass DCO. The PR was
  created, but its first head `96187af97e0c22e35e0873f77e61911b3dbae7ef`
  omitted the required `Signed-off-by` trailer and is intentionally blocked.
- [x] Confirm the review agent runs; create a concrete requested change if a
  deterministic fix-loop stimulus is needed.
- [x] Confirm the fix agent updates the PR and capture the final head SHA. Fix
  corrected the semantic wording at `f7aa5b1` but declined DCO by policy; the
  equivalent final tree was rewritten as one signed-off commit `fa8d3d1`.
- [x] Wait for both CI jobs, including the four-minute job, to pass on the
  final head. The delayed job completed successfully in 4m06s.
- [x] Confirm approvals from Adam and Fullsend Review apply to final head
  `fa8d3d1` and no review blocker remains.
- [x] Comment `/fs-auto-merge`.
- [x] Confirm the first preflight evidence, model decision, receipt, and
  postflight all bind the same head/base tuple. The model safely escalated
  because the base checkout did not contain the PR patch, and postflight did
  not merge.
- [ ] Confirm the remediated preflight evidence, model decision, receipt, and
  postflight all
  bind the same head/base tuple.
- [ ] Confirm the PR is either merged at that exact head or rejected with a
  specific, correct reason.

## Phase 5 - final review and evidence

- [ ] Re-review the final diff independently against the security contract.
- [ ] Run YAML, Python, shell, schema, Fullsend config, and secret scans.
- [ ] Confirm branch freshness, repository visibility, DCO, checks, reviews,
  merge state, and absence of native standing auto-merge.
- [ ] Add an evidence section with issue, PR, workflow, and decision-receipt
  links.
- [ ] Record remaining production gaps separately from lab success.

## Evidence log

- Repository: https://github.com/ascerra/auto-merge (private)
- Fullsend source under test: `fullsend-ai/fullsend` main commit
  `6aa078bc7dc2a5f0dcf2aea8e78e604e380cb2ff`
- Agents source observed at implementation time: `fullsend-ai/agents` main
  commit `6ffe9c7729cf71f3b6f50f8d894cd8e94df83e4d`
- GCP project number resolved: `855403973659`
- Planned provider: `projects/855403973659/locations/global/workloadIdentityPools/ascerra-auto-merge/providers/gh-ascerra-auto-merge`
- GitHub Apps: triage, coder, and review installed for only
  `ascerra/auto-merge` (installation IDs `162307332`, `162307487`, and
  `162307526`)
- Issue: https://github.com/ascerra/auto-merge/issues/1
- Exercise PR: https://github.com/ascerra/auto-merge/pull/2
- Triage proof run: https://github.com/ascerra/auto-merge/actions/runs/35169161822
- Code proof run: https://github.com/ascerra/auto-merge/actions/runs/35169615563
- Review proof run: https://github.com/ascerra/auto-merge/actions/runs/35170123039
- Initial-head CI run: https://github.com/ascerra/auto-merge/actions/runs/35170121938
- Fix-routing discovery: the generated per-repo config omitted the `fix` role,
  so a real `CHANGES_REQUESTED` event was routed but skipped Fix in run
  https://github.com/ascerra/auto-merge/actions/runs/35170672367. The role is
  now explicitly enabled; it reuses the already installed coder identity.
- Successful Fix run: https://github.com/ascerra/auto-merge/actions/runs/35171095208
- Final-head CI run: https://github.com/ascerra/auto-merge/actions/runs/35171785925
- Final-head Review run: https://github.com/ascerra/auto-merge/actions/runs/35171784869
- First Auto-Merge run: https://github.com/ascerra/auto-merge/actions/runs/35172951894
  safely returned `ESCALATE` for exact tuple
  `main@ce2eb9547b9742315240827dda746acafa3b4292` <-
  `fa8d3d1dfa1fa0d4a6fc36d6578745c80f3e0d73`. The model could not inspect the
  PR patch because the trusted checkout intentionally remained at the base.
  The evidence contract now includes bounded, API-sourced per-file patches;
  missing or oversized patches fail deterministic preflight.
- Auto-Merge decision receipt: pending
