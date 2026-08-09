# Models Concepts (v2)

Original short prose notes, in our own words, describing v2 concepts for natural-language-style queries -- not copied from pydantic's docs.

## Serialization

Pydantic v2 models are serialized with `BaseModel.model_dump()` for a plain dict and `BaseModel.model_dump_json()` for a JSON string, replacing the old `.dict()` and `.json()` methods from v1. For validating and serializing data that isn't a `BaseModel` subclass, v2 introduces the `TypeAdapter` class.

## Configuration

Model configuration in v2 lives on the `model_config` class attribute, which replaced the old `Config` inner class from v1. Behavior toggles that used to live on `Config`, like whitespace stripping and default-value validation, now live as keys on `model_config` under their v2 names.

## Settings Management

Environment-based settings management was split out of the core `pydantic` package in v2. Projects that relied on `pydantic.BaseSettings` need to install the separate `pydantic-settings` package and import `BaseSettings` from there instead after upgrading.

## Validators

Field-level and model-level validation in v2 use the `@field_validator` and `@model_validator` decorators. The v1-era `@validator` and `@root_validator` decorators still work but are deprecated and will eventually be removed.

## Equality and Defaults

Two v2 model instances are only equal if they are the exact same type and have matching field values -- comparing a model to a differently-typed model with identical field values no longer returns `True` the way it sometimes did in v1. Similarly, a field typed `Optional[str]` with no explicit default is a required field in v2; it will not silently default to `None`.
