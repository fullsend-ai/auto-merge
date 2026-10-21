# How the shared merge requirements are enforced

The owner delegates one ordinary file, `docs/example-feature.md`, until the
existing grant expires. All five candidate requirements and REVIEW-QUALITY must
pass. No change-size limit participates in eligibility.

## What lives where

The shared repository supplies the five candidate controls, REVIEW-QUALITY,
native Gemara assessment code, metadata-only judge collector and synthetic tests.
`gemara-auto-merge/config/shared-gate.json` is this consumer's immutable source
pin, owner binding and quality policy. Candidate commits cannot choose them.
The endpoint and read-only username/password are GitHub environment secrets;
the App writer keeps its separate existing environment and credential.

The GitHub adapters are our integration work. `gemara-auto-merge/shared_gate.py`
uses the existing authenticated Review consumer, checks ordinary file modes,
required check identities, discussions, protections and current revisions. The
shared Go library consumes these normalized inputs. It does not authenticate
them itself and its assessment explicitly grants no mutation authority.

## Before enrollment

`gemara-auto-merge.yml` resolves the current PR using forge-owned metadata.
A top-level main-only quality job and the reusable `gemara-shared-gate.yml`
separate collection from assessment in three jobs:

1. **Candidate:** check out the trusted main source, authenticate current Review
   publication and collect bounded PR/check/protection evidence. Never check out
   or execute candidate code.
2. **Quality:** on `main` in the restricted `gemara-policy-reader` environment,
   verify the pinned shared source checksum before loading credentials. Run its
   metadata-only collector with only the MLflow reader credentials in the child
   environment. Two equal fixed-window scans are required. The exported artifact
   contains aggregates and digests, not traces, endpoint or credentials.
3. **Assessment:** use no forge permissions or reader/writer secrets. Build the
   pinned shared Go evaluator without credentials. Run it as UID/GID 65534 in a
   chroot and a network namespace after the isolation probe passes. Retain the
   native combined report and a revision/configuration/freshness-bound receipt.

A hold is a valid assessment outcome, not a passing merge decision. The existing
pilot evaluator ANDs its own authorization with the shared result. The writer
job is skipped on hold. An eligible writer independently rechecks the receipt
again just before requesting the protected queue, including current head/base,
configuration and expiry. It never executes the shared code with its App token.

## Final queue enforcement

The existing required `Gemara pilot queue gate` name and branch protections are
preserved. On `merge_group`, collection and assessment run again against the
trusted base, reviewed head and actual cumulative queue tree. The existing
single-PR queue checks still validate exact tree equivalence and queue membership.

The queue workflow receives **no MLflow credential**. It authenticates an
aggregate from a successful quality-collection job in a recent main-branch pilot
run at this exact source revision. That parent run may still be active while its
writer awaits GitHub's queue. Run identity, attempt, workflow path, source, job
status, artifact metadata and ZIP digest are checked. Both the aggregate and the
new candidate receipt must meet their configured age limits. Missing evidence
or a changed base holds; there is no fallback to an older source or a fixture.

The required gate explicitly fails if shared assessment is missing, skipped or
held. Even a manually queued PR cannot pass that gate with a quality hold. The
writer and queue verifier consume only bounded assessment data authenticated
through GitHub; the JSON receipt is not a standalone signed attestation.

## Experimental limits and acceptance

The judge cohort is experiment-wide scored approvals, not a repository-specific
or current-agent-version accuracy measure. Its 99% threshold and 100-sample floor
are owner-selected demonstration settings, not statistical qualification. No
threshold is lowered to manufacture a live pass.

Local tests cover wrong PR/head/base/run/attempt/configuration, stale/future
receipts, failed controls hidden by passing decisions, artifact tampering and
refusal before mutation. Hosted synthetic tests execute the pinned shared core
inside the real jail at both 94/100 and 99/100. The earlier successful advisory
replay and protected baseline merge are separate proofs.

Live acceptance remains a fresh documentation PR whose five candidate controls
pass while the authentic below-threshold quality result holds. Verify the writer
is skipped and the PR has no queue entry or auto-merge request. A real positive
merge requires the authentic population to meet the unchanged policy.
