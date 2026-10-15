# Minimal autonomy policy trial

This is a test harness, not a supported Fullsend feature or a per-repository
installation requirement. It asks: can readiness and exact-PR evidence cross a
small adapter boundary while Fullsend remains independent of the policy engine?

## Run the offline tests

Requires Python 3.11+ and Go 1.25+ (CI pins Go 1.26.6).
From the repository root:

```sh
python3 experiments/autonomy-platform/build_sdk.py
python3 -m unittest discover -s experiments/autonomy-platform -p 'test_*.py'
```

The first build downloads checksum-pinned Go modules from the public Go proxy;
use `build_sdk.py --offline` after setup. Build and adapter children receive a
clean environment without credentials. Binary, build receipt and reports are
ignored. CI runs only these synthetic tests on an ephemeral hosted runner with
read-only permissions, pinned actions, no secrets/OIDC, credential persistence,
caches or artifact uploads. It never calls GitHub or runs Fullsend/model agents.

The tests cover Off, Shadow, Light and policy-governed modes, shared minimums,
stricter repository profiles, missing/stale/wrong-revision evidence, invalidated
readiness, engine switching, and credential isolation. These are simulations;
all modes emit `mutation_permitted: false` and no authorized actions.

## Run on GitHub

`Autonomy shadow observation` runs from trusted default-branch code after CI or
Fullsend completes, when that run identifies a PR. It can also be dispatched
manually on `main` with a PR number. The job has read-only contents, PR and check
permissions. It does not check out PR code, persist credentials or upload reports.
Open the run's Summary to see readiness and candidate controls for both adapters.
A green workflow means collection/evaluation completed; a `hold` is a policy
result, not a workflow failure. This job is not a required merge check.

The lab configuration enables only Fullsend Review. The old custom agent remains
disabled and its supplementary workflow stays paused. Automatic runs may occur
before Review publishes its results; dispatch again afterward when necessary.

## Observe a real PR locally in shadow mode

After the setup is landed and normal Fullsend Review dispatch restored, open a harmless PR changing
only `docs/example-feature.md`, wait for CI and Fullsend Review, then run:

```sh
python3 experiments/autonomy-platform/github_observe.py --pr NUMBER
```

The observer is fixed to public `fullsend-ai/auto-merge` and `main`. It makes
bounded GET-only requests to GitHub's API; it refuses redirects and fails closed
on incomplete pagination or a changing candidate. If authentication is needed,
supply an approved read credential through GH_TOKEN/GITHUB_TOKEN in the local
environment. Never paste credentials into arguments, reports or this repository.
The observer never executes PR code, reads workflow logs, downloads artifacts,
posts comments/statuses, changes branch rules, or requests a merge.

A local ignored `out/github-*/report.json` contains normalized assessments from
both adapters, source/policy hashes, head/base revisions and reasons. Raw API
bodies, patches, review text, actor identities and credentials are not retained.
Repeat after a new revision/review to compare the reasons. Do not commit reports.

**Expected result: hold.** GitHub check observations and Review bot metadata are
available, but trusted findings/risk, meaningful-test sufficiency, execution
assurance, promotion history and status-publication proof remain unknown. Bot
login metadata is not a production attestation; a hash is not a signature.
GitHub rules are observed and hashed, not installed or treated as fully evaluated.

## Implementation boundaries

- `github_observe.py`: reads GitHub and normalizes evidence; always shadow.
- `platform_lab.py`: closed lab profiles, revision binding and adapter dispatch.
- `sdk/`: pinned native Gemara assessment, evidence and aggregation helpers.
- `policies/`: local shared/repository test profiles, not Gemara Policy documents.
- The independent JSON adapter demonstrates engine substitution without invoking
  Gemara; it is a test reference, not another production engine.

Native SDK pin: [go-gemara commit 5e33fda](https://github.com/gemaraproj/go-gemara/tree/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2).
Assessment predicates are authored by this lab and passed to the SDK; Gemara does
not automatically know GitHub or Fullsend semantics. General policy imports,
exceptions and central distribution are not implemented. See
[scope and known compatibility limit](../../docs/attempts/02-policy-evaluation/README.md).

## Why there is Go code here

Gemara's SDK supplies assessment execution, evidence collection and aggregation.
It does not supply a Fullsend Review or GitHub CI checker. `sdk/main.go` attaches
our normalized observations to those native helpers. `platform_lab.py` supplies
the experimental mode/profile and readiness binding. These scripts are a lab
implementation of an integration boundary, not code every repository should copy.

The alternative adapter is `native-json-reference`: a small independent Python
evaluator used to test that the boundary is not tied to Gemara. It is not OPA,
Kyverno, Cedar or a second installed service. Only `gemara-sdk` calls Gemara.

Upstream describes this division in its [integration FAQ](https://gemara.openssf.org/faq/#how-do-evaluation-tools-connect-to-gemara):
existing tools may need glue to emit Gemara evaluation results. Merely authoring
a Policy document does not implement the GitHub/Fullsend evidence checks.
