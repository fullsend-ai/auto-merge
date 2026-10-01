# Merge-queue human-context proof

This intentionally small documentation change exercises the SCM-native
Auto-Merge path after the implementation landed on `main`.

The proof sequence adds a temporary human coordination hold, verifies that the
semantic stage defers, clears the hold, and verifies that GitHub—not the agent—
selects and enforces the repository's merge-queue path.
