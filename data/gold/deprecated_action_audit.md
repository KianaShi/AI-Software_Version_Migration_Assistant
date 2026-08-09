# Stage 8A Audit: deprecated-only vs. actionable migration facts

Systematic check (§2D of the Stage 8A brief) of every `DEPRECATED`/`MOVED`
change record for cases where the gold set said only "X is deprecated" /
"X moved" without capturing the actual recommended migration action, when
the corpus evidence supported a clearer one.

Audited: all `change_type IN ('DEPRECATED', 'MOVED')` records against the
rebuilt corpus (11 total). No other change_types (`REPLACEMENT`,
`REMOVED`, `SIGNATURE_CHANGED`, `BEHAVIOR_CHANGED`) carry a "deprecated
with no action" ambiguity by construction -- `REMOVED` genuinely has no
replacement to state, and the others already require a `replacement_symbol`
or describe a self-contained behavior change.

| Symbol | Type | Before this audit | After | Action added? |
|---|---|---|---|---|
| `BaseModel.from_orm` | DEPRECATED | replacement_symbol=None, evidence said only "deprecated in favor of setting `from_attributes`..." (phrasing too loose for the extractor to capture a target symbol) | → `BaseModel.model_validate`, evidence states the full action: enable `from_attributes` on `model_config`, then call `model_validate()` | **Yes** (§2C) |
| `BaseModel.parse_file` | DEPRECATED | replacement_symbol=None, evidence said only "deprecated with no direct v2 replacement" | → `BaseModel.model_validate`, evidence states: load the file yourself, pass the parsed data to `model_validate()` | **Yes** (§2B) |
| `pydantic.tools.parse_obj_as` | MOVED (was) | replacement_symbol=`pydantic.deprecated.tools.parse_obj_as` -- pointed at a namespace whose own name says "deprecated", not a real recommended migration | changed to DEPRECATED → `TypeAdapter` (the real recommended replacement per the official migration guide); legacy import path kept as a secondary sentence, not the primary action | **Yes** (§2A) |
| `@root_validator` | DEPRECATED | → `@model_validator` | unchanged -- already had a real action | No (already correct) |
| `@validator` | DEPRECATED | → `@field_validator` | unchanged -- already had a real action | No (already correct) |
| `BaseModel.parse_raw` | DEPRECATED | → `BaseModel.model_validate_json` | unchanged -- already had a real action | No (already correct) |
| `BaseSettings`, `color`, `error_wrappers.ValidationError`, `utils.to_camel`, `utils.to_lower_camel` | MOVED | all already had a `replacement_symbol` (import path) | `utils.to_camel`'s target was factually wrong (§1A), not action-less -- fixed as a factual correction, not an action-completeness gap | No (correctness fix, not an action-completeness gap; see main Stage 8A log entry) |

**Conclusion**: 3 of 11 records were deprecated/moved-only without a
supported action (`from_orm`, `parse_file`, `parse_obj_as`); all 3 now
carry the real recommended action, sourced from the same official
migration guide facts already grounding the rest of the corpus -- nothing
invented. The remaining 8 already had actions from Stage 7. No record was
left "status-only" where the corpus evidence could have supported more.
