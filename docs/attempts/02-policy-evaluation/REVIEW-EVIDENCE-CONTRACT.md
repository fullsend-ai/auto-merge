# Review evidence contract — repository-local Fullsend experiment

Status: **hosted repository-local producer and authenticated consumer demonstrated**,
not a centrally shipped Fullsend feature. [PR #43's hosted trial](HOSTED-VENDORED-REVIEW.md)
published native evidence and the automatic Gemara shadow workflow verified it.
Its result held; no native-path merge is claimed. The earlier full merge used the
older receipt route. See [current state](CURRENT-STATE.md).

## What D3 changes

Instead of making every repository reconstruct a Review run from comments,
Fullsend's trusted host should publish one bounded, versioned result. Gemara
methods consume that evidence; a separate host authorizes any forge action.
The producer may be native Fullsend while the choice of policy engine remains
independent. Rego and Privateer are not dependencies of this implementation.

The source additions live in
[`review-evidence-producer/`](../../../gemara-auto-merge/review-evidence-producer/).
The builder reads immutable Fullsend source, applies the repository-owned overlay
in an isolated copy inside this repo and builds `.fullsend/bin/fullsend`. The
original upstream checkout is not changed. The deployed binary, build receipt and
host lock are committed; dependency caches and the isolated source copy are ignored.

The active installation runs local defaults and that binary under an immutable
upstream authentication wrapper. The trusted post-script publishes the bounded
native artifact after validated review state is finalized. This is a hosted lab
extension with pinned source/overlay identity, not an unmodified upstream feature
or a wholly self-contained workflow host. Read the [hosted chronology](HOSTED-VENDORED-REVIEW.md)
for the deployment and compatibility corrections.

```sh
python3 gemara-auto-merge/build_fullsend_evidence_lab.py --source /path/to/fullsend
python3 gemara-auto-merge/run_review_evidence_examples.py
```

After dependency setup, the builder supports `--offline`. Build children get
an allow-listed environment with no forge, model or signing credentials. The
`review-evidence-lab` command reads only stdin and writes stdout. It has no
network client, signing key or merge operation. It accepts **trusted host input**,
not arbitrary model output or a PR-provided metadata document.

## Contract v1

The Go types and Python consumer implement a closed, bounded contract. Unknown
fields/versions, duplicate JSON keys at the producer, and invalid types fail.

- `schema_version`: `fullsend-review-evidence/v1`.
- `subject`: repository ID/name, PR, reviewed head, review base and configuration
  commit. These identities must exactly match the consumer's expected context.
- `producer`: lab host kind, Fullsend source commit, overlay digest, workflow
  path, run and attempt. These claims are not self-authenticating.
- `issued_at`: UTC timestamp; the current consumer permits at most 600 seconds
  of age, rejects future evidence, and does not allow a caller to extend that cap.
  Production lifetime rules require an explicit policy decision.
- `completion`: completed, failed or cancelled. Only a completed record from
  an independently verified successful, still-active run can supply evidence.
- `review`: action, complete findings snapshot (stable ID, severity, category,
  disposition) and optional ordinal risk. An absent risk stays Unknown. An
  approving review with an open finding does not satisfy the findings check.
  Unsupported high/critical human dismissals are refused.
- `payload_sha256`: SHA-256 of canonical ASCII JSON excluding this field, using
  sorted keys and compact separators. It detects alteration; it is not a signature.

This is a findings **snapshot with dispositions**, not a complete historical
event stream or proof that the model found every bug. Review prose, code excerpts,
paths/anchors, private reasoning, arbitrary environment values and credentials
are deliberately excluded. The applied Gemara policy belongs in the evaluation
receipt, not in a reusable Review producer's decision about future consumers.

## Where each fact belongs

| Fact | Actual owner / current collector | Proposed publication | Consumer work remaining |
| --- | --- | --- | --- |
| Reviewed head and base/diff context | Trusted Review host; currently reconstructed from bot review, markers and run/check-suite metadata | `subject` | Compare with current PR and intended assessment revision |
| Run, attempt and host configuration | Trusted workflow host; currently checked against GitHub run, dispatcher and source blobs | `producer`, `subject.configuration_sha` | Authenticate the publisher/run and approved executable/configuration |
| Findings and dispositions | Review host's validated ledger projection; currently parsed from a sticky comment | `review.findings` | Verify completeness/binding and apply findings policy |
| Ordinal risk | Model assessment published by the host; currently a revision-bound lab risk marker | `review.risk` | Treat as model evidence, not an independently established safety fact |
| CI results for the actual revision | Forge/CI producer | Separate CI evidence, not fabricated by Review | Verify revision, required jobs, completion and trusted producer |
| Test sufficiency | Test report producer plus owner-approved criteria | Separate assessment inputs | A green job, zero tests or skipped tests do not establish sufficiency |
| Runtime isolation | Execution platform | Separate platform assurance | Verify approved runtime/isolation evidence; this prototype does not provide it |
| Readiness/promotion and approved scope | Repository/organization owners | Governed policy/configuration | Evaluate readiness separately from pilot eligibility |
| Final authorization and action | Privileged merge host plus native forge protections | Evaluation/enforcement receipt | Revalidate state, scope, expiry and exact-head request; enforce queue checks |

## Verification and trust boundary

`review_evidence_contract.consume` requires a verifier-owned `PublicationProof`
as well as an expected subject. It does not accept `trusted=true` or a proof
copied from the input JSON. The proof must bind the payload digest, producer,
subject, completed successful run and current active/supersession state.
The hosted lab obtains these facts from authenticated GitHub artifact/run metadata,
exact subject bindings and expected host/source checks in `native_review_artifacts.py`.
Production integration still needs an approved publisher and lifecycle/trust model;
a producer claim or unsigned self-digest alone is insufficient.

The local replay deliberately supplies **synthetic publication proof** and tests
the actual binary/evaluator. It is distinct from the successful hosted trial,
which verified real publication metadata. Neither is production certification. Recomputing a forged record's self-digest cannot match the separately
verified digest. Signatures, if adopted, still need subject, freshness, approved
signer, revocation and supersession checks. Authentic origin does not make a
model's risk estimate or review conclusion correct.

The consumer supplies AM-REVIEW, AM-FINDINGS and AM-RISK to native Gemara.
Missing/unverified inputs remain Unknown; authentic high risk or open findings
fail the corresponding requirements. Results bind subject, policy and request
digests. The replay's other candidate inputs are explicitly synthetic. It
assesses PR eligibility only and never manufactures repository qualification.

## What can disappear, and what cannot

With actual native publication and verified retrieval, per-repo parsing of
sticky history, prose markers, encoded findings and a separate risk marker can
be removed. The producer can publish one result directly from host-owned state.
The lab consumer demonstrates that path without parsing any comment.

Publisher authentication, subject/context comparison, findings/risk semantics,
current CI, policy selection, readiness, scope, expiry and forge-state checks
remain necessary. The exact replacement for GitHub run/source reconstruction
depends on the eventual supported publication interface. The lab already removes
comment parsing from the active native path, but retains GitHub provenance and
host-source checks; those checks do not disappear merely because evidence is JSON.

## Supported Fullsend implementation handoff (F1; not filed)

The lab demonstrates automatic Review publication/retrieval; upstream productization
and native command-triggered parity remain separate. The following are requirements
for that supported interface, not claims of changes made upstream:

1. Publish from the trusted host after validated Review state is finalized,
   without taking run identity or metadata from the agent. Bind failed/cancelled
   runs explicitly and avoid publishing a partial record as completion.
2. Choose an authenticated artifact/API and access/retention model. Specify
   supersession, reruns, relevant context changes and compatibility/versioning.
3. Support automatic and command-triggered Review through the same contract.
4. Demonstrate authenticated retrieval, tampering/refusal and invalidation before
   replacing the legacy observer path. Never make readiness green merely because
   this publisher exists.

No upstream changes, issues or PRs were made for the hosted producer/consumer trial.
Rego, complyctl and Privateer equivalence remain outside this implementation.
