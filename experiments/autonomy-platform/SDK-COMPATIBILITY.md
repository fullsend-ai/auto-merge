# Observed SDK compatibility boundary

Pinned SDK: `v0.11.1-0.20261009030221-5e33fda460a8` at
`5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2`, declaring schema v1.5.0.
Validator: official Gemara v1.6.0 schemas with pinned CUE v0.17.1.

## Executed successfully

Native `AssessmentStep`, `EvidenceCollector`, `ControlEvaluation.Evaluate` and
aggregation helpers assessed the lab's normalized observations. Their results,
bound into a complete EvaluationLog, passed v1.6.0 validation. Independent
adapter comparisons cover required pass/hold cases, stale input and typing.
Decoded assessment logs correctly return Unknown instead of re-executing the
functions whose names were recorded. A failed sibling remains failed while a
later sibling is still assessed.

## Reproduced incompatibility

1. Generate a Policy for the lab's effective candidate rules.
2. Validate it against the official v1.6.0 Policy schema: passed.
3. Decode and encode it through native `gemara.Policy` using the pinned SDK.
4. Validate the encoded result against the same schema: rejected.

The inspected output adds empty/default structures, including assessment-plan
method executors with empty identities and type `Invalid`. The source Policy
did not contain these executors. The output also adds an empty scope `out`.
Imports and the input technology scope survive, but the document is not a
schema-valid round trip for this tested input.

Reproduce after setup, with no network or credentials:

```sh
python3 -m unittest discover -s experiments/autonomy-platform -p test_platform.py -k serialization_gap
```

The test expects and records this rejection; it does not strip fields or claim
that the exported Policy is usable. Unknown Policy fields are rejected rather
than silently discarded. This is an observed compatibility/serialization gap,
not proof that every SDK feature fails, or a determination whether the cause is
the schema-version difference, a serializer defect, or both.

Decision: reuse tested assessment helpers, keep schema validation at the
boundary, and do not use this unmodified SDK round trip as the policy-authoring
or general policy-resolution path. Investigate a supported version pair or an
upstream fix with this reproducer. No upstream issue or PR was posted.
