# EasyCode 1.0 Product Ledger

## Current objective

Reduce authoring ceremony without creating a second source language or weakening runtime diagnostics.

## Decisions

- Keep `ProgramDocument` as the only editable program truth.
- Treat Chinese as the primary presentation and discovery layer, not persisted source text.
- Add transient keyboard intent input that emits ordinary typed Program commands.
- Normalize safe condition shorthand into explicit typed predicates; never swallow structural failures as `false`.
- Deliver arbitrary “execute until” as an atomic structural template built from existing loop/call/if/break semantics.
- Expose the already-existing project-function parameter and return model through a transactional author UI.
- Prefer discoverability for existing coordinate/color operations; add only genuinely missing frame-region comparison capabilities.

## Evidence reviewed

- `PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `design.md`
- `docs/TEST_HARNESS.md`
- `docs/DECISIONS.md`
- `docs/vnext/PROGRAM_MODEL.md`
- `docs/vnext/PROGRAM_SEMANTICS.md`
- `docs/vnext/EXPRESSIONS.md`
- `docs/vnext/EXPRESSION_SYNTAX.md`
- `docs/vnext/VARIABLES.md`
- `docs/vnext/FUNCTIONS.md`
- `docs/vnext/IDE_UX.md`
- `docs/vnext/STRUCTURED_BATCH_EDITING.md`

## Unknowns resolved

- JavaScript and Python truthiness disagree; EasyCode uses a documented typed conversion table instead.
- A visually inline call cannot become a hidden runtime call; it expands to one visible call plus one condition in a single transaction.
- “Execute until” must be bounded and observe before acting to avoid unnecessary input.
- Project function signatures are already represented in the core model; the missing product slice is safe editing and cross-call impact handling.

## Deferred

- A full editable text source language.
- Arbitrary record/object truthiness.
- A separate official function for every action-until combination.
- Persisting runtime image samples in variables or Player profiles.
