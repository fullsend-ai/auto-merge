# Auto-Merge Experiments Lab

This public repository is a **Fullsend + Gemara integration lab**. The active
experiment uses native Gemara catalogs and policies to evaluate PR evidence,
with a bounded documentation auto-merge pilot. The older custom auto-merge model
agent is disabled. This is not a production auto-merge service or an approved
organization-wide standard.

## Start here

1. **[Current state and verified proof](docs/attempts/02-policy-evaluation/CURRENT-STATE.md)** — what runs, what was demonstrated, and what remains unknown.
2. [Follow the native Review evidence](docs/attempts/02-policy-evaluation/SHADOW-OBSERVATION.md) — Fullsend approval can still produce a Gemara hold.
3. [Bounded live pilot](docs/attempts/02-policy-evaluation/DOCUMENTATION-AUTO-MERGE-PILOT.md) — owner authorization, App writer and protected merge queue.
4. [Implementation and local commands](gemara-auto-merge/README.md) — policy files, supported semantics and tests.
5. [Documentation map](docs/README.md) — current guides, historical attempts and future proposals.

## Two separate hosted proofs

- **Protected automatic merge:** [PR #41](https://github.com/fullsend-ai/auto-merge/pull/41)
  demonstrated automatic Review, lab-App queue entry and a protected merge using
  the earlier verified receipt path.
- **Native evidence publication and consumption:** [PR #43](https://github.com/fullsend-ai/auto-merge/pull/43)
  exercised a real hosted vendored Fullsend Review. Its native artifact was
  independently verified by the automatic Gemara shadow workflow. The result
  was **hold**, despite an approval: an open finding failed policy and eligible
  change classification was unestablished.

A successful merge through the newer native-artifact path has **not** yet been
demonstrated. General production readiness remains **hold**. The current-state
page links exact runs, revisions, artifacts and assessment results.

## What runs

Fullsend Review → trusted native evidence publisher → authenticated collector →
Gemara evaluation → separately authorized lab App writer → GitHub protected queue.
The newest hosted proof reaches evaluation and holds; the earlier pilot proof
reaches merge. The model has no merge credential. GitHub enforces the final merge.

The automatic cohort is limited to `docs/example-feature.md`, at most 20 changed
lines, and expires **October 22, 2026 at 2 p.m. EDT**. Maintenance is disabled.
Scope and expiry live in
[owner-controlled settings](gemara-auto-merge/config/documentation-auto-merge-settings.json);
these settings are separate from the Gemara policies. Editing policy, workflow or
implementation files is not an eligible documentation-pilot change.

The active Review uses a supported post-script override under the pinned upstream
authentication wrapper, with the normal Fullsend runtime installation path.
See [the post-script evidence path](docs/attempts/02-policy-evaluation/POST-SCRIPT-REVIEW-EVIDENCE.md)
for local validation and the hosted proof still required. Queue entry uses a dedicated repository-scoped lab App; Fullsend-native
queue-writer credential handoff remains separate work. No personal token is used
by this pilot's Actions writer.

## Local verification

```sh
python3 scripts/validate_example.py
```

See the [implementation runbook](gemara-auto-merge/README.md#run) for pinned
Gemara toolchain setup and tests. Local replay uses synthetic inputs and grants
no merge authority. Historical hosted records are not fresh merge authorizations.

## History and safety

[Attempt 1](docs/attempts/01-agent-led/README.md) preserves the earlier agent-led
approach, its contracts and recordings. Historical diagrams and future design
proposals do not describe the active Gemara path unless explicitly stated.
Never commit credentials, environment files or raw sensitive workflow data.
