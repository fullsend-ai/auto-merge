# Review evidence through a post-script override

Prepared October 19, 2026. This replaces the active custom-binary dependency;
PR #43 remains historical proof of the earlier v1 producer. The v2 path requires
its own hosted validation after deployment. General production readiness remains
**hold**. No new upstream Fullsend feature is claimed.

## Active path

1. The existing pinned upstream Fullsend wrapper runs the official runtime through
   its normal installation path. No `.fullsend/bin/fullsend` or root `bin/fullsend`
   is committed. The existing local composite action still retains the bounded artifact.
2. The Review harness inherits the official agent harness with `base:` and overrides
   `post_script: scripts/post-review-gemara.py`. This is a derived Review using
   supported composition, not a new reviewing model.
3. The wrapper preserves the pinned official Review post-script plus the existing
   risk/publication hook. Successful official posting invokes the Python publisher.
4. The publisher checks the current PR head/base/configuration and its pinned source
   digest, then calls the existing Python contract validator/encoder directly.
   There is no `review-evidence-lab` child command or custom Fullsend build.
5. Actions publishes `fullsend-review-evidence-<attempt>` with one bounded JSON file.
   The independent collector verifies run/context, artifact digest, locked host
   source, producer identity and freshness before Gemara assessment.

The wire contract is `fullsend-review-evidence/v2`. Producer kind is
`fullsend-post-script-lab`; `publisher_sha256` identifies the host publisher rather
than falsely reporting a compiled binary overlay. The v1 validator remains for
historical examples, but a new v2 host cannot authorize an old v1 producer by
silently falling back. Missing or mismatched publication remains unknown/hold.

The existing `vendor-evidence-lock.json` filename is retained to keep the observer's
native-path enablement fail-closed. Its schema is now `review-post-script-host/v1`.
It pins host files and the new `review-evidence-producer.json`. The consumer also
refuses a vendored binary reintroduced into the current or original producer tree.
Regenerate these pins after changing a locked source:

```sh
python3 gemara-auto-merge/configure_review_postscript.py
```

## What is unchanged

Policy rules, owner cohort/expiry, model permissions, App scope, queue enforcement
and the workflow authentication wrapper are unchanged. The dedicated lab App,
not Gemara or the Review model, requests protected queue entry. No new credentials,
permissions, dependencies or model calls are introduced for evidence encoding.

The publisher keeps an allowlisted result projection: no model prose, raw
credentials or environment dumps are added to this artifact. Its SHA-256 is an
integrity field, not a signature or independent authentication.

This change intentionally retains the existing bounded evidence artifact. Extending
Fullsend's canonical `agent-result.json` with trusted host metadata remains a
separate upstream proposal; this repository-only change does not implement that
platform-wide schema/lifecycle feature.

## Verification and remaining proof

The local suite exercises publication without any Fullsend binary; an independent
consumer accepts the v2 record with supplied trusted publication proof. Negative
cases cover changed PR head, invalid risk, altered publisher, unsafe destinations,
reserved metadata injection, open findings, wrong producer and host-source drift.
These use synthetic forge responses. They are not evidence of a new hosted Review.

After deployment, inspect a real Review on an existing suitable PR: confirm normal
runtime installation, the post-script v2 publication message, artifact retention,
then an independent shadow result. Do not relabel PR #43's old v1 artifacts as v2.
