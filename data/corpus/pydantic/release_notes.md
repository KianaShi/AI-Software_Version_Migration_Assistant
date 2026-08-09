## v2.0.0

- `BaseModel.dict()` was replaced by `BaseModel.model_dump()`.
- `BaseModel.parse_obj()` was replaced by `BaseModel.model_validate()`.
- `orm_mode` was renamed to `from_attributes`.
- `pydantic.BaseSettings` was moved to `pydantic_settings.BaseSettings`; install the `pydantic-settings` package separately.
- `@validator` is deprecated in favor of `@field_validator`.
- `@root_validator` is deprecated in favor of `@model_validator`.
- `Config` was replaced by `model_config`.
- `pydantic.generics.GenericModel` was removed.
- `regex` was renamed to `pattern` on `Field`.
- `Optional` fields without an explicit default are now required.

## v1.10.10

- Final v1.10.x maintenance release before the v2.0 series; no breaking changes relative to earlier 1.10.x releases.
