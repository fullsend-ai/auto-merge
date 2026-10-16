# Example feature

Status: ready

## Why

This baseline document gives the integration lab a deterministic, low-risk
artifact for agent-authored changes.

## Behavior

In lab-automatic mode, Auto-Merge writes a pending receipt, repeats every gate,
and requests an exact-head squash merge only after review, required CI, and the
configured policy all pass for the same revision.

The exact-head attestation flow keeps correctness, security, and intent
judgment with the Fullsend Review Agent. Auto-Merge verifies that the Review
result is legible and bound to this revision before queue entry.

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
