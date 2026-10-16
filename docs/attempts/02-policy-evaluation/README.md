# Attempt 2: native Gemara policy evaluation

The current work replaces the comparison trial with one Gemara-native path:
ControlCatalog → common Policy → repository Policy → bound evidence → native
EvaluationLog → shadow decision. See the [runbook](../../../gemara-auto-merge/README.md)
and [walkthrough](SHADOW-OBSERVATION.md).

Policies are now actual schema-validated Gemara documents. Repository assessments
are additive to imported common assessments; the host no longer composes a custom
JSON rules profile. GitHub/Fullsend data collection and method implementations
remain evaluator glue. The SDK provides native types and assessment execution,
not a ready-made GitHub merge checker.

The configured scope/import/plan/parameter path is implemented. Unsupported
native features hold explicitly; the runbook names them. This is not a claim to
implement all Gemara semantics or every governance layer. Risk acceptance is not
inferred from a review comment or an unimplemented policy field.

The trial uses official schemas matching the SDK's declared v1.5.0 version.
It validates native inputs and outputs without depending on the earlier SDK
Policy serialization round trip. That historical v1.6 compatibility finding has
not been dismissed or declared universally fixed.

Only Fullsend Review is enabled in the lab. The legacy custom auto-merge agent
and supplementary context workflow remain disabled. The observer has read-only
permissions and no merge/status writer. It consumes the official v2 finding
ledger and a lab host risk-receipt extension, verifying the exact revision,
completed producer run/attempt and pinned configuration. The complete live verifier
requires the positive candidate to pass and negative CI to hold, while both remain
unqualified for autonomous merging. Production attestations, actual merge execution
and human promotion remain separate work; no readiness requirement is bypassed.

The previous comparison implementation and larger research are retained locally
and in version history. They are no longer part of the active evaluation path.
