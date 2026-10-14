# Public-repository safety boundary

The default demo is local and fixture-only. It has no merge operation, forge
client, model client, token lookup, workflow dispatcher or result publisher.
It does not import the existing collector or finalizer. Its result contract is
deliberately different from Attempt 1's mutation-capable result contract.

The separate platform experiment now prepares legacy-registration/route
disabling changes and a fixture-only workflow; the original scripts remain.
Those changes have not been activated on remote main. Do not attach
this experiment to their credentialed execution paths. A future PR can trigger
existing repository automation; adding a safe fixture demo does not make those
workflows safe for arbitrary changed code. Review that automation before any
push or PR, and use the repository's authorization controls. The separate
[platform safety boundary](../autonomy-platform/README.md#publishing-and-activation-boundaries)
explains the new CI definition and the required trusted-main transition.

## Inputs and outputs

- Bundled examples are fabricated and labeled synthetic. No customer records,
  private source content, copied event payloads or live provider responses are
  included.
- Input size, field sets, types, identifiers and record counts are bounded.
  Duplicate JSON keys, extra fields and real-data provenance are rejected.
- A fixture trust label is not an authentication claim. Only this non-mutating
  experiment accepts it. Every recommendation has `mutation_permitted: false`
  and an empty authorized-action list.
- Required missing, stale, conflicting, unknown or unsupported evidence cannot
  become a passing result. All observed refusal reasons are retained.
- Output paths must resolve inside ignored `out/`; symlinks and existing
  destination directories are rejected. This protects repository controls and
  existing retained runs from accidental overwrite.
- Diagnostics are fixed error codes. Rejected data, environments and CUE
  diagnostics are not printed. Public work logs contain commands and summaries,
  not terminal transcripts or environment dumps.

## Tool boundary

`tool-lock.json` pins the Gemara commit, schema hashes, CUE archive and binary
digests. Vendored CUE definitions include the upstream Apache-2.0 license.
Validation checks these pins and invokes only that binary against local files.
Its process environment contains PATH and LANG only. Schema URI strings are
data; the evaluator does not dereference them or run imported commands.

Bootstrap is an explicit network/setup step to a pinned public tool release.
It sends no application credentials, ignores inherited proxy configuration,
verifies the archive before using it, and extracts only the expected executable
entry. The binary stays ignored. This checksum trust boundary depends on the
reviewed lock file and publisher; it is not a substitute for tool provenance
or a full supply-chain audit.

## What remains outside this experiment

Production use needs independently verified source identities, authenticated
attestations, protected policy provenance, observation completeness, durable
storage, concurrency control, queue-revision handling, final revalidation and
verified outcomes. The fixture runner implements none of those authorities.

The local public-content check is defense in depth, not a guarantee that every
possible secret encoding is detected. Human review remains necessary before
publication. No live workflow, merge, model inference or result upload is part
of the walkthrough.
