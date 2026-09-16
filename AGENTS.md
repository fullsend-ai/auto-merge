# Repository instructions

This repository is a private Fullsend Auto-Merge integration lab.

## Scope

- Make only the change requested by the current issue or review.
- Preserve the Fullsend workflow, custom agent, security contract, and CI
  fixtures unless the issue explicitly asks to change them.
- Do not add dependencies for documentation-only changes.
- Never add credentials, tokens, `.env` files, generated identity documents,
  or copied GitHub event payloads.

## Validation

For changes to `docs/example-feature.md`, run:

```bash
python3 scripts/validate_example.py
```

The example document must:

- begin with `# Example feature`;
- contain `Status: ready`;
- contain `## Why`, `## Behavior`, and `## Verification` headings; and
- contain no `TODO`, placeholder, or secret-like text.

All commits must carry a DCO `Signed-off-by` trailer.

