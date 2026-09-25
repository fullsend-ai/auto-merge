# Auto-Merge security contract

Status: normative for this public lab; production Fullsend requires a separate
implementation review.

## Purpose

Auto-Merge adds a semantic authorization policy that an SCM cannot derive from
branch settings alone. It does not decide whether GitHub's mechanical merge
requirements passed.

The question it answers is:

> Given the Review Agent's decision, assessed risk, current human context, and
> repository instructions, is unattended merge appropriate for this exact
> revision now?

## Separation of responsibilities

GitHub exclusively owns:

- required status checks and their conclusions;
- required approving reviews and code-owner rules;
- conversation-resolution requirements;
- branch freshness, conflicts, and mergeability;
- merge method, native auto-merge, and merge-queue execution; and
- the final decision to accept, wait, queue, reject, or merge a request.

Auto-Merge exclusively adds:

- an exact-head attestation from the repository's configured semantic review
  provider (Fullsend Review is the default lab provider);
- the configured provider's structured risk assessment and rationale;
- interpretation of ordinary human context, including an informal request to
  pause, coordinate, sequence, or follow up;
- optional repository-scoped Review quality evidence;
- repository-specific semantic instructions; and
- a revision-bound authorization receipt that can be invalidated when any of
  that semantic context changes.

The collector intentionally does not fetch check runs, required reviews,
rulesets, unresolved-thread state, mergeability, or native auto-merge state.
Those facts remain GitHub's job. The portable agent has no queue-time callback;
GitHub owns the queue after native auto-merge is requested.

## Authority boundary

The Auto-Merge model has no GitHub credential and no mutation authority. The
trusted pre-script collects evidence outside the sandbox. The model returns
`AUTHORIZE`, `DEFER`, or `ESCALATE`. The trusted post-script validates the
result and may submit an exact-head native auto-merge request.

An authorization is bound to:

```text
(repository, pull_request_number, head_sha, base_ref, base_sha,
 policy_fingerprint, semantic_fingerprint, context_fingerprint)
```

The `semantic_fingerprint` covers the Review attestation, risk assessment,
human signals, quality evidence, and repository semantic policy. The broader
`context_fingerprint` detects any evidence-document tampering. A changed head,
base, policy, comment, risk artifact, or quality input makes the prior decision
stale.

## Flow

```text
Review approval or trusted human context event
  -> trusted pre-script collects semantic evidence
     -> missing/stale/out-of-policy semantic input: skip model
     -> otherwise: run Auto-Merge in a read-only sandbox
        -> DEFER / ESCALATE: record outcome; do not contact SCM merge API
        -> AUTHORIZE: trusted post-script recollects semantic evidence
           -> changed: abort
           -> unchanged: write pending receipt
              -> recollect once more
                 -> changed: abort
                 -> unchanged: request GitHub native auto-merge for exact head
                    -> GitHub enforces its rules and direct-or-queue path
```

"Preflight" in this lab means the trusted pre-script's semantic prerequisite
check. It is not a second implementation of SCM policy.

## Semantic prerequisites

The pre-script may skip model invocation only for facts needed to create a
safe, meaningful semantic decision:

1. The target is an open, non-draft, same-repository pull request within the
   configured repository and base branch.
2. The Review Agent approved the exact head SHA.
3. A trusted risk artifact can be correlated to that Review run and is within
   the repository's configured unattended-risk ceiling.
4. When Review quality mode is `enforce`, the supplied metric meets the
   configured score and sample-size threshold.

It does not wait for CI or inspect branch policy. Running before CI finishes is
safe because `gh pr merge --auto` delegates waiting and queue admission to
GitHub.

The prerequisite evaluator runs a fixed sequence and writes a structured
`prerequisites.checks` array. Each entry has an `id`, `label`, `status`, and
`detail`; the sequence covers supported modes, pull-request state and revision
identity, repository/base scope, current semantic attestation and review
summary, current risk evidence, bounded human context, risk-policy validity and
ceiling, and optional review-quality policy. The existing `failures` array is
retained as a compact machine-readable list.

Receipts render that ordered evidence as `✅` passed checks, `ℹ️` checks that are
not applicable because a prerequisite is missing, and `❌` checks that blocked
Auto-Merge. The Fullsend pre-script puts the blocking `❌` checks first in its
single-line skip reason so the hosted status cannot hide the reason behind a
long list of passes; it relays the complete ordered array as
`auto_merge_checks`, because the line-oriented pre-script protocol does not
support multiline values.

## Semantic decision

- `AUTHORIZE`: the current semantic context permits unattended merge.
- `DEFER`: a human pause, timing dependency, sequencing need, or follow-up can
  be resolved without changing the patch.
- `ESCALATE`: evidence is contradictory, risky, suspicious, or requires human
  judgment.

The model accepts the configured review provider's approval as the code-review
decision. It does not inspect the patch or repeat code review. It interprets context that
SCM configuration cannot understand, such as “please do not merge until the
release owner confirms the rollout.”

## Human context

Ordinary PR conversation comments are bounded and passed as untrusted evidence.
A PR author, owner, member, or collaborator can express an informal veto or
coordination requirement without knowing how to file a formal changes-requested
review. A later explicit clearance can resolve it. Formal review and inline
review state remain GitHub's responsibility and are not reinterpreted here.

Untrusted outsiders cannot unilaterally veto a merge. Their text remains
visible to the agent so a concrete safety concern can be escalated. Control
commands and Fullsend machine comments are excluded from this context.
Trusted comments have a separate evidence budget and can never be displaced by
an outsider comment flood. If trusted context itself exceeds that bound,
authorization fails closed.

## Optional Review quality evidence

Repositories may configure quality evidence as:

- `off`: no external quality source is required;
- `observe`: expose available evidence to the agent without a hard gate; or
- `enforce`: skip authorization unless score and sample thresholds pass.

This POC defines and tests the contract but does not yet fetch MLflow itself.
Production should use a trusted adapter that emits a signed or otherwise
authenticated repository/reviewer/version/time-window aggregate. No MLflow
credential belongs in the sandbox or evidence document.

## GitHub submission and merge queue

After fresh semantic revalidation, trusted host code runs:

```text
gh pr merge <number> --auto --squash --match-head-commit <head_sha>
```

This requests native auto-merge; it does not perform a privileged bypass. If
the repository requires a merge queue, GitHub enrolls the PR. If direct merge
is permitted, GitHub follows that path. If SCM policy is unsatisfied, GitHub
waits or rejects the request.

The portable agent has no queue-specific callback or required status check. Once
the trusted post-script requests native auto-merge, GitHub owns the direct or
merge-queue path and all checks on any queue-generated revision. A future
platform-owned integration may reauthorize semantic state on a queue-generated
revision, but that is outside this repository's shippable agent contract.

## Fail-closed behavior

No SCM request is made when:

- the model output is invalid or does not exactly copy the binding;
- the Review approval or risk assessment is missing or stale;
- risk or enforced Review quality exceeds repository policy;
- semantic context changes after the model decision;
- the target is a fork or outside the configured lab repository; or
- GitHub rejects the exact-head native auto-merge request.

## Known POC limitations

- The current Review risk comment lacks a structured head SHA, so this lab
  requires the trusted exact-head Review summary, risk comment, and GitHub
  approval to be updated in that order within a one-minute window. This is
  stronger than timestamp-only approval correlation but remains a POC bridge.
  Production should emit one structured Review attestation containing the head
  SHA, review decision, risk fields, and run identity.
- The lab merge queue is configured to merge one PR per group. Production must
  resolve and reauthorize every PR when a forge supports multi-PR merge groups.
- Durable lease, receipt storage, crash reconciliation, and dedicated GitHub
  App identity remain production work.
- The optional Review quality adapter is specified but not connected.
- The context rerun workflow is GitHub-specific and should become a forge
  driver event in Fullsend.

## Explicit non-goals

- Reimplementing or imposing SCM branch policy.
- Treating the absence of repository protections as an Auto-Merge error.
- Parsing CI results, required-review counts, rulesets, or mergeability in the
  Auto-Merge agent.
- Giving a model forge credentials or mutation tools.
- Supporting the legacy `CODE_AUTO_MERGE` path.
