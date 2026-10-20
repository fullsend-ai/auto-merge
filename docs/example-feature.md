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
A baseline run must review the current head and retain its findings and risk.
Successful CI is not a substitute for a completed Fullsend Review.
Shared integration wiring is tested only after the installed Review path works.
