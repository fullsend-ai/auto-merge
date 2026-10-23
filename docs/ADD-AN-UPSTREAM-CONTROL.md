# Add one maintained control to an existing auto-merge policy

This experiment adds **OSPS-QA-03.01: Address Pass/Fail Checks Before Accepting
Changes** from the OpenSSF OSPS Baseline. It runs for a PR, without adding a
repository-readiness scan. It catches an optional failing automated check even
when the existing required checks are green.

## Owner flow

1. Use the locally modified Fullsend build supplied at `.fullsend/bin/fullsend`.
   Its source patch and reproducible build settings are recorded in
   `.fullsend/local-build.json`. The standard Fullsend action selects this
   vendored binary. This is an experiment, not a released Fullsend feature.
2. Keep the current owner policy. Select the additional requirement:

   ```yaml
   auto_merge:
     mode: shadow
     policy: fullsend-default
     controls:
       - OSPS-QA-03.01
   ```

3. For managed installations, put that same block under the repository's
   `config:` in repos.yaml (or `defaults.config` to inherit it). Use the local
   Fullsend build for manifest operations. The usual management path materializes
   `.fullsend/config.yaml`; do not hand-edit a managed file.
4. Run `.fullsend/bin/fullsend auto-merge config --config-dir .fullsend` to
   inspect effective settings. `mode: off` overrides an inherited enable;
   `controls: []` clears inherited optional requirements.
5. Run the existing **Gemara shadow observation** workflow with a PR number.
   Its selected-control step writes a job summary and native log without needing
   an active merge grant. It returns success when the observation was valid, even
   when the control reports failed or the configured mode holds writes.
   Then run the existing PR flow. The Gemara pilot summary lists OSPS-QA-03.01;
   the `gemara-evaluation` artifact includes `upstream-evaluation-log.json`,
   the effective policy and normalized evidence. Shadow evaluates and holds
   write requests; it never asks the App to enroll a PR.
6. `mode: enforce` allows the selected requirement to participate in the existing
   writer decision. All existing grants, review, quality and protected-queue
   requirements still apply. This setting cannot renew the expired lab grant.

## What was reused, and what we supplied

The upstream requirement is pinned to OSPS release v2026.08.28, commit
`a26a7963f6fd098c1e82829322ec9e1196a4f294`. Its original YAML and license are
retained unchanged under `gemara-auto-merge/upstream/osps-baseline/`.
The SDK transport wrapper selects that control without rewriting its text or
applicability. It does not imply compliance with all maturity-2 controls.

OpenSSF maintains the control content. Gemara supplies the schema/SDK and native
evaluation log. We supplied the GitHub evidence adapter, the Fullsend selector
and the integration with our existing writer. We did not install Privateer or
reuse its scanner implementation. This demonstrates selecting a supported,
prepackaged control; arbitrary upstream controls still need suitable adapters.

The adapter examines GitHub check runs and commit-status contexts for the exact
revision. A failure, pending check, incomplete API response, or lack of evidence
holds. Completed neutral/skipped runs do not clear an earlier failed check.
Reruns are resolved by latest actual pass/fail result for each producer/context.
No automatic manual-bypass exception is supported, so this is stricter than the
upstream allowance for explicit manual bypass.

At queue time the adapter checks the merged revision. It excludes only the
current assessment run's own check suite, identified through forge metadata;
GitHub still requires that queue gate to finish successfully before merging.
The existing App rechecks immediately before requesting enrollment. No new writer
or protection bypass is part of the policy implementation.

## Public sources

- [Pinned upstream requirement](https://github.com/ossf/security-baseline/blob/a26a7963f6fd098c1e82829322ec9e1196a4f294/baseline/OSPS-QA.yaml)
- [Gemara reuse model](https://gemara.openssf.org/faq/)
- [Existing passing-check example PR #54](https://github.com/fullsend-ai/auto-merge/pull/54)
- [Existing failing-check example PR #29](https://github.com/fullsend-ai/auto-merge/pull/29)

Those PRs were observed read-only using the prepared local implementation. They
are not a claim that this setup is deployed or that either PR was newly merged.
The old automatic owner grant expires on 2026-10-22 at 18:00 UTC and is retained.
