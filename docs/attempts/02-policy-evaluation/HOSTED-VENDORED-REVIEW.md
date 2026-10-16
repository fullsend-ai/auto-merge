# Hosted Review with actual Fullsend vendored mode

Status: installation prepared; the hosted run and authenticated artifact proof
will be recorded here after deployment. No synthetic replay is called hosted proof.

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
