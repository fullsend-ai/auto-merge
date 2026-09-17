# Example feature

Status: ready

## Why

This baseline document gives the integration lab a deterministic, low-risk
artifact for agent-authored changes.

## Behavior

The exercise issue will ask the code agent to extend this section with one
small, reviewable behavior statement.

The Auto-Merge agent may merge a pull request only after an exact-head review approval, all required CI checks, and configured policy gates have passed.

## Verification

Run `python3 scripts/validate_example.py` and confirm both pull-request CI jobs
complete successfully.

