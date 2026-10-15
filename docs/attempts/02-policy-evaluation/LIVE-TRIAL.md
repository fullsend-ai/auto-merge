# Follow the real-PR trial

Start with [PR #28: valid documentation](https://github.com/fullsend-ai/auto-merge/pull/28)
and [PR #29: intentionally failing validation](https://github.com/fullsend-ai/auto-merge/pull/29).
Verified hosted examples:

- [PR #28 after Fullsend approval](https://github.com/fullsend-ai/auto-merge/actions/runs/38667624427): CI and current Review pass; both adapters still hold.
- [PR #29 shadow summary](https://github.com/fullsend-ai/auto-merge/actions/runs/38667019263): stable observation, both adapters hold.

Neither is intended to merge. The negative PR changes the example's Status field,
not application code or workflow permissions.

## What happens

1. GitHub CI validates the example. The valid PR passed; the negative PR failed.
2. Fullsend Review is invoked through the existing official installation.
3. [Autonomy shadow observation](https://github.com/fullsend-ai/auto-merge/actions/workflows/autonomy-shadow.yml)
   reads GitHub metadata from trusted main code. It also supports manual dispatch
   on main with either PR number, useful after Review finishes.
4. The observer normalizes CI, Review metadata and changed-path observations.
5. The Go adapter attaches assessment functions to the native Gemara SDK. The
   independent Python adapter evaluates the same request without using Gemara.
6. The run Summary shows each repository-readiness and PR-candidate assessment.
   A green run means the experiment completed. Read its decision: it can hold.

CI passed on #28 and failed on #29, and both adapters reflected that difference.
After the compatibility fixes, [Fullsend Review succeeded](https://github.com/fullsend-ai/auto-merge/actions/runs/38667018391)
and approved #28's exact revision. Both adapters then reported CI and Review
passed, with findings/risk missing. That is expected: approval metadata alone is
not the complete evidence contract for autonomous merging.
Both overall decisions hold while required evidence is missing. Readiness is a
separate question from whether this particular PR looks acceptable.

## Why policies alone were not enough

Gemara supplies the model, schemas and SDK helpers. A tool still needs to know
how to collect GitHub data and how to judge Fullsend evidence. That is why this
trial contains Go assessment functions; they are our integration code, not a
second implementation of Gemara. See the [official integration FAQ](https://gemara.openssf.org/faq/#how-do-evaluation-tools-connect-to-gemara).

The current shared/repository JSON profiles are explicitly experimental; they
are not native Gemara Policy documents. This trial proves SDK assessment and
an engine boundary against live metadata. It does not prove general Gemara
policy resolution, a centrally distributed standard, or that all this host
scaffolding belongs in Fullsend. Those remain design questions informed by the
trial. The earlier Policy serialization/version compatibility limit also remains.
Do not turn the closed profile composer into a new Fullsend policy language;
establish how to consume native policies through a supported evaluator before
promoting that scaffolding into a platform feature.

## Who would install what?

A future shared Fullsend integration should own evidence collection and engine
invocation; repositories should select modes and policy references through small
configuration. That rollout is a proposed direction, not an available feature.
The Python alternative is a test reference, not OPA/Cedar/Kyverno or an installed
service. It demonstrates that an engine can be replaced without giving it forge
write credentials or merge authority.

## Safety and observed corrections

Only Fullsend Review is enabled in the lab. The old custom auto-merge agent and
supplementary context route remain disabled. The observer is read-only, checks
out trusted main only and publishes normalized job summaries. No raw API bodies,
patches, review text or credentials are saved in the trial reports or this doc.

The first live run led to a pending-CI correction: unfinished checks are Unknown;
a completed unsuccessful check fails the CI predicate. Initial Review jobs also
exposed a dispatcher/manifest version mismatch; its official pin was refreshed.
The next Review attempt exposed stale copied Vertex provider/profile definitions.
Those were removed using Fullsend's documented migration to built-in providers;
the disabled legacy harness now names `vertex-ai` directly.
No credentials or auth modes were changed. Temporary admin bypasses used to land
reviewed main updates were removed immediately, and original rules were verified.

## Questions the live evidence leaves open

- What supported Fullsend contract supplies a complete revision-bound finding
  ledger and risk attestation? The trial can observe approval but does not
  convert a review body or risk comment into trusted authority.
- Which Gemara-compatible evaluator should execute native Policy scope, imports
  and exceptions? The tested SDK assessment helpers do not establish that path.
- Who produces and approves repository readiness/promotion evidence? Accessible
  rules and green CI do not prove meaningful testing, runtime assurance or a
  sufficient shadow history.

Those are the next platform/integration questions; the lab does not answer them
by inventing passing evidence or enabling autonomous merges.
