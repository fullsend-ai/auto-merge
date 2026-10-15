# Attempt 2: minimal policy-boundary trial

Goal: learn whether Fullsend can supply normalized evidence to Gemara for
repository readiness and PR eligibility, without coupling Fullsend to one engine.
See the [runbook](../../../experiments/autonomy-platform/README.md).

## What this change tests

- Shared minimums plus repository restrictions in a closed experimental profile.
- Native Gemara assessment/evidence helpers versus an independent JSON adapter.
- Separate readiness and candidate decisions bound to configuration, policy,
  engine and time; the candidate also binds the exact head/base revisions.
- Four-mode behavior using synthetic evidence; only read-only shadow observation
  of real GitHub PRs. Every mode forbids mutation in this experiment.

## What it does not establish

The profiles and their composition are local scaffolding, not native Gemara
Policy execution or an approved company standard. There is no policy registry,
GitHub rules installer, signed qualification, trusted status publisher, automatic
observer workflow, Fullsend platform API, or merge controller implementation.
A real PR should hold while readiness, finding or risk evidence is missing.

Earlier research found a Policy serialization compatibility gap between the
pinned SDK (declares schema v1.5.0) and official v1.6.0 schemas. The broader
reproducer is retained locally, outside this minimal trial. This change exercises
assessment helpers, does not round-trip Policy documents, and makes no claim of
v1.6.0 schema validation. Establishing a supported version pair remains open.

Per-repository rollout should eventually require small configuration and policy
references; these lab scripts should become shared integration work if the
experiment supports that direction. They are not an installation template.

## Safety and next experiment

The legacy agent registration is disabled and its context workflow is gated off.
Both legacy dispatch workflows were also manually paused before PR publication.
Merging does not restore them. Verify the landed configuration before restoring
normal Fullsend Review dispatch; leave the legacy auto-merge route disabled.
Then open a harmless docs PR, let Fullsend Review assess it, and run the local
read-only observer. Do not change required checks or infer merge permission.

The larger initial evaluator, retained outputs, schemas, vendor probe and planning
material were removed from the proposed change and preserved in local research.
The original attempt's ADR/security documents have not been moved or rewritten.
