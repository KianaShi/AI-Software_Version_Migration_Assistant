# Pydantic Gold Set v2 — Human Review Checklist

Generated from `data/gold/pydantic_gold_queries.json` against the live corpus/entities.db, rebuilt fresh by this script (Stage 8A remediation commit). For each query, review:

1. Is the query itself reasonable/realistic?
2. Are `required_change_ids` correct and complete?
3. Does the evidence text actually support the query, and does the recommended migration action (not just the deprecation label) look right?
4. Is `query_type` the right taxonomy bucket?

⚠️ = flagged taxonomy (multi_change / underspecified_symbol / behavioral_change / negative) — highest mislabeling risk, review these first. `legacy_symbol` and `single_change`/`exact_symbol` are lower risk (Stage 8A already split out the genuinely ambiguous case as `underspecified_symbol`).

Note: `multi_change` means multiple changes co-occurring within the single 1.10.x→2.x transition this benchmark covers -- **not** version-path multi-hop (v2→v3→v4→v5), which this corpus cannot test and isn't claimed anywhere in this checklist.

---

## behavioral_change ⚠️ (3 queries)

### `q_behav_01`
**Query**: Why do two models with the same field values no longer compare equal in v2 if they're different classes?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_54b690481be24182` — **BaseModel.__eq__** (BEHAVIOR_CHANGED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_1563a7ece0a1cced` [MIGRATION_GUIDE] — `BaseModel.__eq__` behavior changed in v2.0.0: two instances only compare equal when they share the exact same type in addition to matching field values.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_behav_02`
**Query**: My pydantic dataclass used to accept a tuple for a nested field and now raises a validation error in v2 -- why?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_999d076fe177c512` — **dataclasses** (BEHAVIOR_CHANGED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_106711a3466a584a` [MIGRATION_GUIDE] — `pydantic.dataclasses` validation behavior changed in v2.0.0: tuples are no longer accepted as input for nested fields; use dicts instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_behav_03`
**Query**: Why does `Field()` raise a validation error on extra keyword arguments now instead of just passing them through?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_6a2dc66d8dc05c78` — **Field** (SIGNATURE_CHANGED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=None

**relevant_evidence_ids**:
- `ev_7e9724f7dfd4b61f` [MIGRATION_GUIDE] — `Field()` no longer accepts arbitrary keyword arguments for JSON schema; use the `json_schema_extra` parameter instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## config_change (3 queries)

### `q_config_01`
**Query**: Is the `Config` inner class still used for model configuration in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_8c18bf30e55d23e6` — **Config** (REPLACEMENT). **Migration action: use `model_config`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_30c55c829f8e2ca6` [MIGRATION_GUIDE] — `Config` was replaced by `model_config` in v2.0.0.
- `ev_32801bae97fe5369` [RELEASE_NOTE] — `Config` was replaced by `model_config`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_config_02`
**Query**: I set `allow_mutation = False` on my model's `Config` -- what's the v2 equivalent?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_c26e897728a752e6` — **allow_mutation** (REPLACEMENT). **Migration action: use `frozen`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_32b947a000d56ab1` [MIGRATION_GUIDE] — `allow_mutation` was replaced by `frozen`, with inverted meaning, in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_config_03`
**Query**: I pass extra keyword arguments to `Field()` for JSON schema metadata -- does that still work in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_6a2dc66d8dc05c78` — **Field** (SIGNATURE_CHANGED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=None

**relevant_evidence_ids**:
- `ev_7e9724f7dfd4b61f` [MIGRATION_GUIDE] — `Field()` no longer accepts arbitrary keyword arguments for JSON schema; use the `json_schema_extra` parameter instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## dependency_change (5 queries)

### `q_dep_01`
**Query**: My project imports `BaseSettings` from `pydantic` -- what package do I need for v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_0e5dbf6bbecb76af` — **BaseSettings** (MOVED). **Migration action: use `pydantic_settings.BaseSettings`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_7476d82cf221065c` [MIGRATION_GUIDE] — `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings` in v2.0.0; install the separate `pydantic-settings` package.
- `ev_8eea20663bbd8bd0` [RELEASE_NOTE] — `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings`; install the `pydantic-settings` package separately.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_dep_02`
**Query**: I use `pydantic.color` types in my models -- what do I need to install for v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_82085d42f6875a45` — **color** (MOVED). **Migration action: use `pydantic_extra_types.color`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_30f358d7d90407bc` [MIGRATION_GUIDE] — `pydantic.color` was moved to `pydantic_extra_types.color` in v2.0.0; install the separate `pydantic-extra-types` package.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_dep_03`
**Query**: My code catches `pydantic.error_wrappers.ValidationError` -- where does that live in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_b273756303613c54` — **error_wrappers.ValidationError** (MOVED). **Migration action: use `ValidationError`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_24f527ff528b22fd` [MIGRATION_GUIDE] — `pydantic.error_wrappers.ValidationError` was moved to `pydantic.ValidationError` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_dep_04`
**Query**: I use `pydantic.utils.to_camel` -- where did it move in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_9b083f10c0e8b6b4` — **utils.to_camel** (MOVED). **Migration action: use `alias_generators.to_pascal`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_cf2a07b970d04a95` [MIGRATION_GUIDE] — `pydantic.utils.to_camel` was moved to `pydantic.alias_generators.to_pascal` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_dep_05`
**Query**: How should I replace `pydantic.tools.parse_obj_as` in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_2c59160cad89f6d4` — **tools.parse_obj_as** (DEPRECATED). **Migration action: use `TypeAdapter`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_586c4afe8ba65cce` [MIGRATION_GUIDE] — `pydantic.tools.parse_obj_as` is deprecated in favor of `TypeAdapter` in v2.0.0. The legacy function remains importable at `pydantic.deprecated.tools.parse_obj_as`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## exact_symbol (8 queries)

### `q_exact_01`
**Query**: What happened to `BaseModel.dict()` in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_576c51189b348218` — **BaseModel.dict** (REPLACEMENT). **Migration action: use `BaseModel.model_dump`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_652888a764e37a78` [MIGRATION_GUIDE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()` in v2.0.0.
- `ev_755df9df6f83b414` [RELEASE_NOTE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_02`
**Query**: What replaced `BaseModel.parse_obj()` in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_7107f5995efa5a72` — **BaseModel.parse_obj** (REPLACEMENT). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_b1a013459e35afe2` [MIGRATION_GUIDE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()` in v2.0.0.
- `ev_d58abc65ea83cdfa` [RELEASE_NOTE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_03`
**Query**: Is `BaseModel.copy()` still available in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_4bec5de3a791b4aa` — **BaseModel.copy** (REPLACEMENT). **Migration action: use `BaseModel.model_copy`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_c6570b96830c1dc3` [MIGRATION_GUIDE] — `BaseModel.copy()` was replaced by `BaseModel.model_copy()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_04`
**Query**: What is the v2 equivalent of `BaseModel.construct()`?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_cdb5bd04644c800d` — **BaseModel.construct** (REPLACEMENT). **Migration action: use `BaseModel.model_construct`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_61ccb45292681b2e` [MIGRATION_GUIDE] — `BaseModel.construct()` was replaced by `BaseModel.model_construct()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_05`
**Query**: How do I replace `BaseModel.json()` when upgrading to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_cfb91b3e1e4ff0f9` — **BaseModel.json** (REPLACEMENT). **Migration action: use `BaseModel.model_dump_json`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_0f40640698d6e9a5` [MIGRATION_GUIDE] — `BaseModel.json()` was replaced by `BaseModel.model_dump_json()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_06`
**Query**: Is the `@validator` decorator still recommended in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_b068027c29b10d68` — **@validator** (DEPRECATED). **Migration action: use `@field_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_bca5bfd474977aea` [RELEASE_NOTE] — `@validator` is deprecated in favor of `@field_validator`.
- `ev_fd505c6d0201ea86` [MIGRATION_GUIDE] — `@validator` is deprecated in favor of `@field_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_07`
**Query**: What should I use instead of `@root_validator` in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_51e749a61a7c0496` — **@root_validator** (DEPRECATED). **Migration action: use `@model_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_27565fdbbc6dcefe` [RELEASE_NOTE] — `@root_validator` is deprecated in favor of `@model_validator`.
- `ev_86b0153189e69b4a` [MIGRATION_GUIDE] — `@root_validator` is deprecated in favor of `@model_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_exact_08`
**Query**: What replaced `BaseModel.update_forward_refs()` in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_ce6917189d569425` — **BaseModel.update_forward_refs** (REPLACEMENT). **Migration action: use `BaseModel.model_rebuild`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_e98a7a9dd077a136` [MIGRATION_GUIDE] — `BaseModel.update_forward_refs()` was replaced by `BaseModel.model_rebuild()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## legacy_symbol (3 queries)

### `q_amb_02`
**Query**: Where did `validator` go in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_b068027c29b10d68` — **@validator** (DEPRECATED). **Migration action: use `@field_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_bca5bfd474977aea` [RELEASE_NOTE] — `@validator` is deprecated in favor of `@field_validator`.
- `ev_fd505c6d0201ea86` [MIGRATION_GUIDE] — `@validator` is deprecated in favor of `@field_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_amb_03`
**Query**: What's the relationship between `root_validator` and `model_validator`?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_51e749a61a7c0496` — **@root_validator** (DEPRECATED). **Migration action: use `@model_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_27565fdbbc6dcefe` [RELEASE_NOTE] — `@root_validator` is deprecated in favor of `@model_validator`.
- `ev_86b0153189e69b4a` [MIGRATION_GUIDE] — `@root_validator` is deprecated in favor of `@model_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_amb_04`
**Query**: Is `Config` still a thing in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_8c18bf30e55d23e6` — **Config** (REPLACEMENT). **Migration action: use `model_config`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_30c55c829f8e2ca6` [MIGRATION_GUIDE] — `Config` was replaced by `model_config` in v2.0.0.
- `ev_32801bae97fe5369` [RELEASE_NOTE] — `Config` was replaced by `model_config`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## multi_change ⚠️ (6 queries)

### `q_multi_01`
**Query**: A model class calls both `.dict()` and `.parse_obj()` -- what needs to change to migrate it to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_576c51189b348218` — **BaseModel.dict** (REPLACEMENT). **Migration action: use `BaseModel.model_dump`**. version_to=2.0.0
- `chg_7107f5995efa5a72` — **BaseModel.parse_obj** (REPLACEMENT). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_652888a764e37a78` [MIGRATION_GUIDE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()` in v2.0.0.
- `ev_755df9df6f83b414` [RELEASE_NOTE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()`.
- `ev_b1a013459e35afe2` [MIGRATION_GUIDE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()` in v2.0.0.
- `ev_d58abc65ea83cdfa` [RELEASE_NOTE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_multi_02`
**Query**: My codebase uses both `@validator` and `@root_validator` extensively -- what's the full v2 upgrade path?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_b068027c29b10d68` — **@validator** (DEPRECATED). **Migration action: use `@field_validator`**. version_to=2.0.0
- `chg_51e749a61a7c0496` — **@root_validator** (DEPRECATED). **Migration action: use `@model_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_bca5bfd474977aea` [RELEASE_NOTE] — `@validator` is deprecated in favor of `@field_validator`.
- `ev_fd505c6d0201ea86` [MIGRATION_GUIDE] — `@validator` is deprecated in favor of `@field_validator` in v2.0.0.
- `ev_27565fdbbc6dcefe` [RELEASE_NOTE] — `@root_validator` is deprecated in favor of `@model_validator`.
- `ev_86b0153189e69b4a` [MIGRATION_GUIDE] — `@root_validator` is deprecated in favor of `@model_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_multi_03`
**Query**: I have a settings class subclassing `BaseSettings` and other models calling `.dict()` -- what all changes for v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_0e5dbf6bbecb76af` — **BaseSettings** (MOVED). **Migration action: use `pydantic_settings.BaseSettings`**. version_to=2.0.0
- `chg_576c51189b348218` — **BaseModel.dict** (REPLACEMENT). **Migration action: use `BaseModel.model_dump`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_7476d82cf221065c` [MIGRATION_GUIDE] — `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings` in v2.0.0; install the separate `pydantic-settings` package.
- `ev_8eea20663bbd8bd0` [RELEASE_NOTE] — `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings`; install the `pydantic-settings` package separately.
- `ev_652888a764e37a78` [MIGRATION_GUIDE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()` in v2.0.0.
- `ev_755df9df6f83b414` [RELEASE_NOTE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_multi_04`
**Query**: I use `GenericModel` for generics and `ConstrainedStr` for string constraints -- how do both migrate to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_86caad279cb88679` — **generics.GenericModel** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0
- `chg_a2fa2bd4b7b59a90` — **ConstrainedStr** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_d7c943c68632e72f` [RELEASE_NOTE] — `pydantic.generics.GenericModel` was removed.
- `ev_e43947ebd65b2700` [MIGRATION_GUIDE] — `pydantic.generics.GenericModel` was removed in v2.0.0; subclass `BaseModel` and `Generic` directly instead.
- `ev_3ef91e857e9f1e9c` [MIGRATION_GUIDE] — All `Constrained*` classes, such as `pydantic.ConstrainedStr`, were removed in v2.0.0; use `Annotated` with `Field` constraints instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_multi_05`
**Query**: My code imports `pydantic.color` and catches `pydantic.error_wrappers.ValidationError` -- what import paths change in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_82085d42f6875a45` — **color** (MOVED). **Migration action: use `pydantic_extra_types.color`**. version_to=2.0.0
- `chg_b273756303613c54` — **error_wrappers.ValidationError** (MOVED). **Migration action: use `ValidationError`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_30f358d7d90407bc` [MIGRATION_GUIDE] — `pydantic.color` was moved to `pydantic_extra_types.color` in v2.0.0; install the separate `pydantic-extra-types` package.
- `ev_24f527ff528b22fd` [MIGRATION_GUIDE] — `pydantic.error_wrappers.ValidationError` was moved to `pydantic.ValidationError` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_multi_06`
**Query**: I call `.json()` and `.copy()` on models throughout my app -- what's the full v2 migration for both?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_cfb91b3e1e4ff0f9` — **BaseModel.json** (REPLACEMENT). **Migration action: use `BaseModel.model_dump_json`**. version_to=2.0.0
- `chg_4bec5de3a791b4aa` — **BaseModel.copy** (REPLACEMENT). **Migration action: use `BaseModel.model_copy`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_0f40640698d6e9a5` [MIGRATION_GUIDE] — `BaseModel.json()` was replaced by `BaseModel.model_dump_json()` in v2.0.0.
- `ev_c6570b96830c1dc3` [MIGRATION_GUIDE] — `BaseModel.copy()` was replaced by `BaseModel.model_copy()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## natural_language (6 queries)

### `q_nl_01`
**Query**: How do I turn a model instance into a plain dictionary now?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_576c51189b348218` — **BaseModel.dict** (REPLACEMENT). **Migration action: use `BaseModel.model_dump`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_652888a764e37a78` [MIGRATION_GUIDE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()` in v2.0.0.
- `ev_755df9df6f83b414` [RELEASE_NOTE] — `BaseModel.dict()` was replaced by `BaseModel.model_dump()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_nl_02`
**Query**: What's the new way to build a model instance while skipping validation?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_cdb5bd04644c800d` — **BaseModel.construct** (REPLACEMENT). **Migration action: use `BaseModel.model_construct`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_61ccb45292681b2e` [MIGRATION_GUIDE] — `BaseModel.construct()` was replaced by `BaseModel.model_construct()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_nl_03`
**Query**: How do I validate a plain dict into a model object now?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_7107f5995efa5a72` — **BaseModel.parse_obj** (REPLACEMENT). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_b1a013459e35afe2` [MIGRATION_GUIDE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()` in v2.0.0.
- `ev_d58abc65ea83cdfa` [RELEASE_NOTE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_nl_04`
**Query**: What's the current recommended way to write a field-level validator function?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_b068027c29b10d68` — **@validator** (DEPRECATED). **Migration action: use `@field_validator`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_bca5bfd474977aea` [RELEASE_NOTE] — `@validator` is deprecated in favor of `@field_validator`.
- `ev_fd505c6d0201ea86` [MIGRATION_GUIDE] — `@validator` is deprecated in favor of `@field_validator` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_nl_05`
**Query**: How can I make a copy of a model instance in the new version?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_4bec5de3a791b4aa` — **BaseModel.copy** (REPLACEMENT). **Migration action: use `BaseModel.model_copy`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_c6570b96830c1dc3` [MIGRATION_GUIDE] — `BaseModel.copy()` was replaced by `BaseModel.model_copy()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_nl_06`
**Query**: How do I resolve forward-referenced types after all my models are defined?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_ce6917189d569425` — **BaseModel.update_forward_refs** (REPLACEMENT). **Migration action: use `BaseModel.model_rebuild`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_e98a7a9dd077a136` [MIGRATION_GUIDE] — `BaseModel.update_forward_refs()` was replaced by `BaseModel.model_rebuild()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## negative ⚠️ (5 queries)

### `q_neg_01`
**Query**: Does `BaseModel` still exist as the main way to define a schema in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**: _(none — negative query)_

**relevant_evidence_ids**: _(none)_

**stability_evidence_ids** (proves nothing changed, not an extracted change):
- `chunk_6b79a0f330c14283` [OFFICIAL_DOCS] — Subclassing `BaseModel` remains the primary way to define a schema in pydantic v2, the same as in v1.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_neg_02`
**Query**: If I explicitly set a default value with `Field(default=...)`, does that field still work the same way in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**: _(none — negative query)_

**relevant_evidence_ids**: _(none)_

**stability_evidence_ids** (proves nothing changed, not an extracted change):
- `chunk_236901f84adcb3af` [OFFICIAL_DOCS] — A field given an explicit default value, such as `Field(default=None)`, continues to behave the same way in v2; only fields with no explicit default changed.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_neg_03`
**Query**: Is pydantic v2 still installed with `pip install pydantic`?
**from/to version**: 1.10 → 2.0

**required_change_ids**: _(none — negative query)_

**relevant_evidence_ids**: _(none)_

**stability_evidence_ids** (proves nothing changed, not an extracted change):
- `chunk_14f5df59233c17d5` [OFFICIAL_DOCS] — The core `pydantic` package is still installed with `pip install pydantic` in v2 -- only optional add-ons like settings management and extra types moved to separate packages.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_neg_04`
**Query**: Can a `BaseModel` field still be typed as another `BaseModel` subclass (nested model composition) in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**: _(none — negative query)_

**relevant_evidence_ids**: _(none)_

**stability_evidence_ids** (proves nothing changed, not an extracted change):
- `chunk_f385868fdf1ec4c9` [OFFICIAL_DOCS] — Nested model composition, typing a field as another `BaseModel` subclass, is still supported in v2.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_neg_05`
**Query**: Is custom field-level validation still supported in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**: _(none — negative query)_

**relevant_evidence_ids**: _(none)_

**stability_evidence_ids** (proves nothing changed, not an extracted change):
- `chunk_a352286f25b071d6` [OFFICIAL_DOCS] — Custom field-level validation is still supported in v2 via `@field_validator`; only the decorator name changed from v1's `@validator`.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## single_change (8 queries)

### `q_single_01`
**Query**: I'm on pydantic 1.10 and use `allow_mutation` in my model config -- what do I change for v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_c26e897728a752e6` — **allow_mutation** (REPLACEMENT). **Migration action: use `frozen`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_32b947a000d56ab1` [MIGRATION_GUIDE] — `allow_mutation` was replaced by `frozen`, with inverted meaning, in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_02`
**Query**: My code subclasses `GenericModel` for generic pydantic models -- how do I migrate this to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_86caad279cb88679` — **generics.GenericModel** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_d7c943c68632e72f` [RELEASE_NOTE] — `pydantic.generics.GenericModel` was removed.
- `ev_e43947ebd65b2700` [MIGRATION_GUIDE] — `pydantic.generics.GenericModel` was removed in v2.0.0; subclass `BaseModel` and `Generic` directly instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_03`
**Query**: I use `ConstrainedStr` for constrained string fields -- what's the v2 migration path?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_a2fa2bd4b7b59a90` — **ConstrainedStr** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_3ef91e857e9f1e9c` [MIGRATION_GUIDE] — All `Constrained*` classes, such as `pydantic.ConstrainedStr`, were removed in v2.0.0; use `Annotated` with `Field` constraints instead.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_04`
**Query**: My project uses `pydantic.stricturl` -- what do I need to change in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_0ac9b1e08e434d62` — **stricturl** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_3a43580e16d854b4` [MIGRATION_GUIDE] — `pydantic.stricturl` was removed in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_05`
**Query**: I have type hints using `pydantic.NoneStr` -- how do I migrate to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_2c3efcf57e49ace0` — **NoneStr** (REMOVED). _(no replacement -- status-only fact; see deprecated_action_audit.md)_. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_533719143c455d0e` [MIGRATION_GUIDE] — `pydantic.NoneStr` was removed in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_06`
**Query**: I call `BaseModel.parse_file()` to load models from disk -- what's the v2 path?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_03c9c34505b4e4a8` — **BaseModel.parse_file** (DEPRECATED). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_30ea86b540cbf0a7` [MIGRATION_GUIDE] — `BaseModel.parse_file()` is deprecated in favor of `BaseModel.model_validate()` in v2.0.0; load the file yourself and pass the parsed data in.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_07`
**Query**: My ORM integration relies on `BaseModel.from_orm()` -- how do I migrate it to v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_496eb868d6bf7606` — **BaseModel.from_orm** (DEPRECATED). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_13e86ccacaae15b2` [MIGRATION_GUIDE] — `BaseModel.from_orm()` is deprecated in favor of `BaseModel.model_validate()` in v2.0.0; set `from_attributes` to `True` on `model_config` first.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

### `q_single_08`
**Query**: I generate JSON schemas with `BaseModel.schema()`. What should I use in v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_bd117c7fa3d4b780` — **BaseModel.schema** (REPLACEMENT). **Migration action: use `BaseModel.model_json_schema`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_4acc026c1661a889` [MIGRATION_GUIDE] — `BaseModel.schema()` was replaced by `BaseModel.model_json_schema()` in v2.0.0.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---

## underspecified_symbol ⚠️ (1 queries)

### `q_amb_01`
**Query**: What happened to `parse` in pydantic v2?
**from/to version**: 1.10 → 2.0

**required_change_ids**:
- `chg_7107f5995efa5a72` — **BaseModel.parse_obj** (REPLACEMENT). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0
- `chg_5fecd7e4efcff8f7` — **BaseModel.parse_raw** (DEPRECATED). **Migration action: use `BaseModel.model_validate_json`**. version_to=None
- `chg_03c9c34505b4e4a8` — **BaseModel.parse_file** (DEPRECATED). **Migration action: use `BaseModel.model_validate`**. version_to=2.0.0

**relevant_evidence_ids**:
- `ev_b1a013459e35afe2` [MIGRATION_GUIDE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()` in v2.0.0.
- `ev_d58abc65ea83cdfa` [RELEASE_NOTE] — `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()`.
- `ev_7faa94eaf774d77e` [MIGRATION_GUIDE] — `BaseModel.parse_raw()` is deprecated in favor of `BaseModel.model_validate_json()`.
- `ev_30ea86b540cbf0a7` [MIGRATION_GUIDE] — `BaseModel.parse_file()` is deprecated in favor of `BaseModel.model_validate()` in v2.0.0; load the file yourself and pass the parsed data in.

**Reviewer notes**: _(query reasonable? / change_ids correct? / migration action correct? / evidence supports it? / taxonomy correct?)_

---
