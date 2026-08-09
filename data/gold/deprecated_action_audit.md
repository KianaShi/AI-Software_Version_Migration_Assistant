# Stage 8A / 8A.1 Audit: deprecated-only vs. actionable migration facts

Systematic check of every `DEPRECATED`/`MOVED`/`REMOVED` change record for
cases where the gold set said only "X is deprecated/moved/removed"
without capturing the actual recommended migration action, when corpus
evidence supported a clearer one. `REPLACEMENT`, `SIGNATURE_CHANGED`, and
`BEHAVIOR_CHANGED` records aren't included here since they either already
require a `replacement_symbol` or self-describe a behavior change, not a
compliance-only status.

Two ways a record counts as "has an action": a `replacement_symbol`
(clean symbol → symbol rename, e.g. `parse_obj` → `model_validate`) or,
added in Stage 8A.1, a free-text `migration_action_text` for
recommendations that aren't a clean symbol swap (e.g. "use dicts
instead", "subclass `BaseModel` and `Generic` directly instead"). Forcing
the latter into `replacement_symbol` would misrepresent them as renames
they aren't -- `migration_action_text` exists specifically so a real
action isn't dropped just because it doesn't fit that shape.

| Symbol | Type | Action | Source |
|---|---|---|---|
| `BaseModel.dict` etc. (8 `REPLACEMENT` facts) | REPLACEMENT | `replacement_symbol` | not in this audit's scope (see note above) |
| `@root_validator` | DEPRECATED | `replacement_symbol` → `@model_validator` | Stage 7 |
| `@validator` | DEPRECATED | `replacement_symbol` → `@field_validator` | Stage 7 |
| `BaseModel.parse_raw` | DEPRECATED | `replacement_symbol` → `BaseModel.model_validate_json` | Stage 7 |
| `BaseModel.from_orm` | DEPRECATED | `replacement_symbol` → `BaseModel.model_validate` | Stage 8A §2C (was `None` -- loose phrasing broke the tight-pattern extractor) |
| `BaseModel.parse_file` | DEPRECATED | `replacement_symbol` → `BaseModel.model_validate` | Stage 8A §2B (was `None` -- "no direct v2 replacement" was the old, incomplete phrasing) |
| `pydantic.tools.parse_obj_as` | DEPRECATED | `replacement_symbol` → `TypeAdapter` | Stage 8A §2A (was `MOVED` → the deprecated import path itself, not a real recommendation) |
| `BaseSettings`, `color`, `error_wrappers.ValidationError` | MOVED | `replacement_symbol` (import path) | Stage 7 |
| `pydantic.utils.to_camel` | MOVED | `replacement_symbol` → `alias_generators.to_pascal` | Stage 8A §1A (was wrong: `to_camel` -- a real fact, not an action-completeness gap) |
| `pydantic.utils.to_lower_camel` | MOVED | `replacement_symbol` → `alias_generators.to_camel` | Stage 8A §1A (added; the real `to_camel` mapping) |
| `pydantic.generics.GenericModel` | REMOVED | `migration_action_text`: "subclass `BaseModel` and `Generic` directly instead" | Stage 8A.1 §1 (was status-only) |
| `pydantic.ConstrainedStr` | REMOVED | `migration_action_text`: "use `Annotated` with `Field` constraints instead" | Stage 8A.1 §1 (was status-only) |
| `pydantic.NoneStr` | REMOVED | `migration_action_text`: "use `str \| None` instead" | Stage 8A.1 §2 (was status-only; `NoneStr` is a documented alias for `None \| str`, so the replacement type is real, not invented) |
| `Field` (arbitrary JSON-schema kwargs) | SIGNATURE_CHANGED* | `migration_action_text`: "use the `json_schema_extra` parameter instead" | Stage 8A.1 §1 (was status-only) |
| `pydantic.dataclasses` (tuple input) | BEHAVIOR_CHANGED* | `migration_action_text`: "use dicts instead" | Stage 8A.1 §1 (was status-only) |
| `pydantic.stricturl` | REMOVED | **none -- intentional** | official migration guide lists no 1:1 replacement for it; gold query (`q_single_04`) rewritten to "Was `pydantic.stricturl` removed in v2?" rather than implying an action exists |

\* `Field` and `pydantic.dataclasses` are technically outside the
`DEPRECATED`/`MOVED`/`REMOVED` scope stated above (they're
`SIGNATURE_CHANGED`/`BEHAVIOR_CHANGED`) but are included here because
they were flagged in the same review round for the identical
status-only-despite-available-action problem.

**Conclusion**: of 15 audited `DEPRECATED`/`MOVED`/`REMOVED` records, 14
now carry a real recommended action (11 via `replacement_symbol`, 3 via
`migration_action_text`); the 1 that doesn't (`stricturl`) is
intentionally status-only because no action is verifiable from the
official source, and the corresponding gold query was reworded rather
than left implying one exists. No record was left incomplete where the
corpus evidence could have supported more, and no action was invented
where the corpus didn't support one.
