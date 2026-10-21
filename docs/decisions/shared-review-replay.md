# Owner decision: manual shared Review replay

Status: owner-approved preparation and hosted testing; merge approval pending.

The repository owner requested the shared Gemara experiment and explicitly
approved DCO commits, pushes, PR/MR tests and necessary tested fixes within
`fullsend-ai/auto-merge`, `ascerra/fullsend-gemara-integration` and the existing
GitLab consumer. The owner's follow-up was: "you can continue I approve just
security check things first".

This decision records that implementation scope for PR #52, specifically:

- `.github/workflows/gemara-shared-review.yml`: a manual, advisory retained
  Review replay, refused on the default branch; no candidate merge authority.
- `scripts/collect_review_replay.py`: read-only GitHub provenance checks and
  bounded data export, with no execution of downloaded code.
- `scripts/run_shared_review.py`: checksum-pinned shared assessment on a
  non-default test branch, without repository write or Fullsend/merge secrets.
- Supporting tests and documentation for these paths and trust boundaries.

The owner required security checks first. Local and hosted CI secret scans,
vulnerability checks, tests and schema checks are recorded in PR #52 and the
companion shared-policy PR. Findings must be resolved on the latest commit.

This record does not substitute for independent review, claim OS isolation,
approve merging this PR, enable a required merge gate, extend an owner grant,
change protections or authorize a new merge writer. Deployment requires the
normal owner-approved PR merge. The existing protected-path human-review
requirement remains in force until that approval is supplied.
