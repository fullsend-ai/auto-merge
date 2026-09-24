# Linked issue evidence smoke test

This documentation-only change verifies that Auto-Merge can connect a pull
request to its same-repository originating issue and provide that issue's
bounded intent to the semantic stage.

The semantic stage should compare the issue request, pull-request intent,
changed-file context, Review Agent rationale, current risk evidence, and any
optional trace references. Issue text is context, not merge authorization.

Closes #14
