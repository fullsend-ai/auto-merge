# Autonomy platform experiments

This is the second phase of Attempt 2: repository qualification, candidate
eligibility and four-mode behavior through a replaceable policy-adapter
boundary. It uses the native Gemara Go SDK and an independently implemented
Python JSON adapter. No adapter, gate or command can request a merge.

This is **experimental lab code**, not a shipped Fullsend API, company-wide
standard, complete evidence verifier or general Gemara policy engine. The
closed profile format is scaffolding for comparison. Gemara Policy documents
are generated and validated; arbitrary native Policy imports, exceptions and
evaluation-method resolution are not implemented by the SDK adapter.

## Run the synthetic experiments

From the repository root, with Python 3.11+ and Go 1.25+:

```sh
python3 experiments/gemara-spike/bootstrap_cue.py
python3 experiments/autonomy-platform/build_sdk.py
python3 -m unittest discover -s experiments/autonomy-platform -p 'test_*.py'
python3 experiments/autonomy-platform/demo.py
```

Bootstrap downloads a checksum-pinned CUE binary. The SDK build downloads
checksum-verified public modules into a temporary cache, verifies modules,
runs its Go tests, and builds an ignored binary. It receives a small clean
environment, no application credentials, no automatic toolchain download and
no Go telemetry. Use `build_sdk.py --offline` after dependency setup.
The evaluator itself runs offline with only PATH and locale in its child.

The SDK is pinned at commit `5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2` /
module `v0.11.1-0.20261009030221-5e33fda460a8`, with dependencies in
[go.mod](sdk/go.mod) and [go.sum](sdk/go.sum). The local
[build record](build-lock.json) binds adapter source and executable hashes.
It is provenance, not a signature or proof of authority.

## What is exercised

- Eight readiness requirements, including rule/check/review visibility,
  trusted status publication, meaningful tests, isolation, native execution
  support and governance-approved shadow history.
- Candidate CI, Review, finding ledger, risk threshold, change class and
  protected-change requirements. Both adapters implement their own checks.
- A shared profile plus a stricter repository profile. Unknown fields,
  excluded minima, weakened thresholds and expanded scope are rejected.
- Qualification invalidation on configuration, policy, adapter or time change.
  Candidate evidence also binds repository, head and base SHA.
- Off, Shadow, Light and policy-governed simulations. Every result has
  `mutation_permitted: false` and no authorized actions. Light and governed
  cases demonstrate policy behavior; they do not activate real merging.
- Native SDK assessment execution, sibling aggregation and evidence capture.
  Generated catalogs, Policies and SDK evaluation output validate against the
  pinned v1.6.0 schemas for the exercised subset.
- A real limit: [SDK Policy round-trip compatibility](SDK-COMPATIBILITY.md).
  Passing assessment output does not prove general SDK/schema compatibility.

Readiness observations in synthetic tests are assumptions. Local unsigned
qualification records cannot be imported as production attestations. Promotion
criteria and meaningful-testing sufficiency require independently produced
evidence and governance; a boolean or green CI status does not establish them.

## Read-only GitHub observation

```sh
python3 experiments/autonomy-platform/github_observe.py --pr 26
python3 experiments/autonomy-platform/launch_check.py
```

The observer is fixed to public `fullsend-ai/auto-merge` and GitHub's API host.
It accepts an approved read credential through GH_TOKEN/GITHUB_TOKEN if
needed. No credential is passed to either adapter. Requests are GET-only;
redirects, oversized responses and incomplete pagination fail closed.
It never executes PR code, fetches workflow logs or downloads artifacts.

The retained report contains closed-domain normalized values, hashes and
reasons. API bodies, review/comment text, patches, identities and event payloads
are not saved. Review bot-login metadata is a useful observation, not a complete
production attestation. Current findings, trusted risk, readiness history,
runtime assurance and status-publication proof remain unknown and hold.

There were no open PRs at the recorded test. The executed observation uses
**closed PR #26** and is explicitly historical, not an active PR trial or a
reconstruction of policy at its merge time. Both engines hold it.
`launch_check.py` compares trusted-main files with the local setup, reports
differences, and always forbids activation. It never changes settings.

## Vendored experiment

```sh
python3 experiments/autonomy-platform/prepare_vendor.py --fullsend-source /path/to/approved/fullsend
```

Requires a clean Fullsend checkout at
`f5934f595239c5c9bb589f9d8e6a3f30a58945d8` and Go 1.26.5+.
This calls Fullsend's own `CollectVendoredAssets` and
`CollectPerRepoInstallFiles` through a temporary Go probe. It compares pinned
upstream routing with local vendored routing and stages content in ignored
`out/`. It neither builds/packages the Fullsend CLI binary nor calls the
installer. This verifies content/routing preparation, not a running vendored
deployment. The source checkout is not modified.

The Go probe receives no credentials. Its temporary module maps Fullsend's
nested mintcore module to the same approved source, avoiding an unrelated
remote module lookup. Staged assets are data for review, never executed.

## Publishing and activation boundaries

The local diff disables the legacy custom-agent registration and its
supplementary semantic-context route. It preserves the old scripts as Attempt 1.
**Trusted remote main is unchanged.** A PR's disabling edits do not disable
the base branch's existing privileged route while that PR is being evaluated.

The new `autonomy-fixtures.yml` is a separate, non-authoritative CI job:
ephemeral hosted runner, contents:read, pinned actions, no secrets or OIDC,
no credential persistence/cache/artifact upload, and synthetic tests only.
It does not run this observer or publish an eligibility status for a real PR.
The fixture workflow may run on the setup PR; it never dispatches the live
observer or a Fullsend agent.

Before publishing a setup PR, inspect active runs and temporarily pause the
existing legacy dispatch paths using reviewed repository settings. Human-review
and land the disabling setup before restoring normal Fullsend Review dispatch.
Then open a harmless active test PR for the shadow observer. Do not make the
fixture job a production autonomy gate or treat it as merge permission.

Publication and workflow-pause history are recorded in the work log. This setup
is for human review, not live activation. Authenticated adapters, native candidate/queue lifecycle,
durable signed evidence and successful native action receipts remain follow-up.

Retained results: [synthetic cases](examples/platform-results.json),
[historical GitHub observation](examples/github-observation.json),
[native vendor preparation](examples/vendor-preparation.json).
See [the work log](../../docs/attempts/02-policy-evaluation/WORKLOG.md) and
[the platform plan](../../docs/attempts/02-policy-evaluation/SPIKE-PLAN.md).
