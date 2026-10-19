# Example feature

Status: ready

## Why

This baseline document gives the integration lab a deterministic, low-risk
artifact for agent-authored changes.

## Behavior

Fullsend Review produces findings and a risk assessment for the PR revision.
The trusted host publishes bounded evidence, and our integration verifies it
before evaluating our Gemara policy. An eligible result alone grants no merge
permission: a separately authorized writer rechecks the current revision and
requests GitHub's protected merge queue.

An owner-authorized documentation trial evaluates policy before queue entry.
The required queue check validates the reviewed document again on the cumulative
merge-group commit before GitHub merges it.

## Verification

Run `python3 scripts/validate_example.py` and confirm both pull-request CI jobs
complete successfully. Failed validation returns a nonzero status.
This line exercises the fast review path without changing merge policy.
A repository-scoped lab App requests queue entry only after Gemara policy passes.
The pilot verifies the reviewed revision separately from its trusted configuration.
The renamed Gemara workflows preserve the documentation-only merge boundary.
