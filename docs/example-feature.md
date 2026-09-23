# Example feature

Status: ready

## Why

This baseline document gives the integration lab a deterministic, low-risk
artifact for agent-authored changes.

## Behavior

In lab-automatic mode, Auto-Merge writes a pending receipt, repeats every gate,
and requests an exact-head squash merge only after review, required CI, and the
configured policy all pass for the same revision.

## Verification

Run `python3 scripts/validate_example.py` and confirm both pull-request CI jobs
complete successfully. Failed validation returns a nonzero status.

The Option 2 test keeps semantic approval with the Fullsend Review Agent and
lets Auto-Merge verify the exact-head attestation before queue entry.
