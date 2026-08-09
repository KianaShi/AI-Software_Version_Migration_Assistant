# Pydantic v1 to v2 Migration Guide

This guide summarizes breaking changes when migrating from pydantic 1.10.x to pydantic 2.x. Original short-form notes grounded in the official migration guide; not copied verbatim from it.

## BaseModel Method Renames

- `BaseModel.dict()` was replaced by `BaseModel.model_dump()` in v2.0.0.
- `BaseModel.json()` was replaced by `BaseModel.model_dump_json()` in v2.0.0.
- `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()` in v2.0.0.
- `BaseModel.copy()` was replaced by `BaseModel.model_copy()` in v2.0.0.
- `BaseModel.construct()` was replaced by `BaseModel.model_construct()` in v2.0.0.
- `BaseModel.update_forward_refs()` was replaced by `BaseModel.model_rebuild()` in v2.0.0.
- `BaseModel.__fields__` was renamed to `BaseModel.model_fields` in v2.0.0.
- `BaseModel.from_orm()` is deprecated in favor of `BaseModel.model_validate()` in v2.0.0; set `from_attributes` to `True` on `model_config` first.
- `BaseModel.parse_raw()` is deprecated in favor of `BaseModel.model_validate_json()`.
- `BaseModel.parse_file()` is deprecated in favor of `BaseModel.model_validate()` in v2.0.0; load the file yourself and pass the parsed data in.
- `BaseModel.schema()` was replaced by `BaseModel.model_json_schema()` in v2.0.0.

## Config Changes

- `Config` was replaced by `model_config` in v2.0.0.
- `allow_population_by_field_name` was renamed to `populate_by_name`.
- `anystr_strip_whitespace` was renamed to `str_strip_whitespace`.
- `orm_mode` was renamed to `from_attributes`.
- `schema_extra` was renamed to `json_schema_extra`.
- `validate_all` was renamed to `validate_default`.
- `allow_mutation` was replaced by `frozen`, with inverted meaning, in v2.0.0.
- `min_anystr_length` was renamed to `str_min_length`.
- `max_anystr_length` was renamed to `str_max_length`.
- The `smart_union` config setting was removed in v2.0.0.
- The `json_loads` config setting was removed in v2.0.0.
- The `json_dumps` config setting was removed in v2.0.0.
- The `underscore_attrs_are_private` config setting was removed in v2.0.0.

## Field Parameter Changes

- The `min_items` parameter of `Field` was renamed to `min_length` in v2.0.0.
- The `max_items` parameter of `Field` was renamed to `max_length` in v2.0.0.
- The `regex` parameter of `Field` was renamed to `pattern` in v2.0.0.
- The `const` parameter of `Field` was removed in v2.0.0.
- The `unique_items` parameter of `Field` was removed in v2.0.0.
- `Field()` no longer accepts arbitrary keyword arguments for JSON schema; use the `json_schema_extra` parameter instead.

## Validator Changes

- `@validator` is deprecated in favor of `@field_validator` in v2.0.0.
- `@root_validator` is deprecated in favor of `@model_validator` in v2.0.0.
- `@validate_arguments` was renamed to `@validate_call` in v2.0.0.
- The `each_item` parameter of `@field_validator` was removed in v2.0.0.
- The `allow_reuse` parameter of `@validator` is no longer necessary in v2.0.0.

## Generic Model Changes

- `pydantic.generics.GenericModel` was removed in v2.0.0; subclass `BaseModel` and `Generic` directly instead.

## Dataclass Changes

- The `__post_init_post_parse__` method was removed in v2.0.0.
- `pydantic.dataclasses` validation behavior changed in v2.0.0: tuples are no longer accepted as input for nested fields; use dicts instead.
- The `__pydantic_model__` attribute was removed from pydantic dataclasses in v2.0.0.

## Moved Symbols (Dependency Changes)

- `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings` in v2.0.0; install the separate `pydantic-settings` package.
- `pydantic.color` was moved to `pydantic_extra_types.color` in v2.0.0; install the separate `pydantic-extra-types` package.
- `pydantic.error_wrappers.ValidationError` was moved to `pydantic.ValidationError` in v2.0.0.
- `pydantic.utils.to_camel` was moved to `pydantic.alias_generators.to_pascal` in v2.0.0.
- `pydantic.utils.to_lower_camel` was moved to `pydantic.alias_generators.to_camel` in v2.0.0.
- `pydantic.tools.parse_obj_as` is deprecated in favor of `TypeAdapter` in v2.0.0. The legacy function remains importable at `pydantic.deprecated.tools.parse_obj_as`.
- `pydantic.PyObject` was renamed to `pydantic.ImportString` in v2.0.0.

## Removed Types

- All `Constrained*` classes, such as `pydantic.ConstrainedStr`, were removed in v2.0.0; use `Annotated` with `Field` constraints instead.
- `pydantic.NoneStr` was removed in v2.0.0.
- `pydantic.stricturl` was removed in v2.0.0.

## Behavior Changes

- `BaseModel.__eq__` behavior changed in v2.0.0: two instances only compare equal when they share the exact same type in addition to matching field values.
- `Optional` fields without an explicit default are now required in v2.0.0; they no longer default to `None` automatically.
- A plain `TypeError` raised inside a validator is no longer converted into a `ValidationError` as of v2.0.0.
- `model_dump_json()` output is compacted by default in v2.0.0, with no spaces after separators.
