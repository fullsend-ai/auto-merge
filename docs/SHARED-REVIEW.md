# Shared Gemara Review check

The shared check runs after authenticated collection, in a separate job with
`permissions: {}` and no Fullsend App, inference or merge credentials. It never
runs inside the write-privileged Review post-script. The existing publisher and
its local degraded-risk guard remain unchanged.

`.fullsend/shared-review-tool.json` explicitly approves the public shared source
by immutable commit, Go module version and content checksum. CI uses patched Go
1.26.9. This dependency belongs to the data-only assessment job; it is not an
addition to Fullsend's harness remote-resource allowlist.

The initial hosted test replays the real retained Review for PR #51. The collector
authenticates the completed Actions run, source publisher, artifact digest and
exact subject. It exports only bounded Review data. The assessment job uses the
shared `project-review` and `check-review` commands and retains the native Gemara
assessment. It checks approval, findings and required risk using the common
`REVIEW-CLEAR` requirement. Missing risk holds with `risk_assessment_missing`.

This is explicitly a retained-review replay, not current-head authorization.
The selected source artifact expires; a missing or changed source fails closed.
Changing the selected example or shared source requires an owner-reviewed diff.

The other four owner requirements, fresh live collection, required enforcement
and the eventual migration of the existing queue writer remain separate work.
This report grants no merge authority. Existing protected queue behavior is
unchanged. The governance change itself needs the normal owner-approved route
before deployment; do not use the documentation pilot or a bypass to install it.

## Replay lifetime and deployment

This workflow is manual (`workflow_dispatch`) and advisory. It replays one
owner-selected artifact retained for 14 days; after expiry it exits with
`replay_source_expired`. It does not run on every candidate or supply a required
merge check. Input artifact names are stable across partial job reruns.

The GitHub run and artifact metadata must match the reviewed PR head and pinned
Fullsend harness. For `pull_request_target`, GitHub's API `run.head_sha` is the
PR head, not the base configuration SHA. The publisher pin and retained record
bind the selected configuration; this replay does not claim independent signed
attestation of execution. Do not use it for current-candidate merge authority.

GitLab retains its own consumer collector and runner setup; this repository's
replay collector supports GitHub only. Shared policy evaluation remains in the
public integration repository. Live enforcement must load scripts, binding and
source pins from the protected default branch and authenticate current evidence.

Owner approval to prepare this milestone does not self-approve its deployment.
Merge through normal owner review before any required check or writer consumes
these changes. No branch-protection bypass is part of this plan.
