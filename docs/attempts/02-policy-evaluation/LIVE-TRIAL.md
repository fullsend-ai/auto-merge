# Follow the real-PR trial

Start with [PR #28: valid documentation](https://github.com/fullsend-ai/auto-merge/pull/28)
and [PR #29: intentionally failing validation](https://github.com/fullsend-ai/auto-merge/pull/29).
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
No credentials or auth modes were changed. Temporary admin bypasses used to land
reviewed main updates were removed immediately, and original rules were verified.
