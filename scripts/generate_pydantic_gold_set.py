import json
import sqlite3
from pathlib import Path

"""
Generate data/gold/pydantic_gold_queries.json against the real
change_id/evidence_id values produced by build_pydantic_benchmark_corpus.
Queries below reference symbol names (looked up here), not raw hash ids,
so a corpus rebuild can't silently desync the gold set from typos.

Taxonomy allocation (48 total): exact_symbol 8, natural_language 6,
single_hop 8, multi_hop 6, config_change 3, dependency_change 5,
behavioral_change 3, negative 5, ambiguous_alias 4.

config_change and behavioral_change are short of the suggested 5 each --
documented honestly rather than padded: bare, non-dotted config-setting
names (`orm_mode`, `schema_extra`, `Optional`, etc.) don't survive
symbol detection by design (see symbol_normalization.py -- a bare
backtick word is treated as a parameter name, not a symbol), so most of
the real Config-setting renames in migration_guide.md never became
UnresolvedChange claims at all. This is a real Level 1 extraction-
coverage finding, not a gold-set-authoring shortcut.

GOLD_QUERIES entries: (query_id, query_text, query_type, symbols,
from_version, to_version). symbols is a list of real symbol_name values
(empty for negative queries); required_change_ids/relevant_evidence_ids
are resolved from it.
"""

DB_PATH = Path("data/entities.db")
OUTPUT_PATH = Path("data/gold/pydantic_gold_queries.json")

GOLD_QUERIES = [
    # --- exact_symbol (8) ---
    ("q_exact_01", "What happened to `BaseModel.dict()` in pydantic v2?", "exact_symbol", ["BaseModel.dict"], "1.10", "2.0"),
    ("q_exact_02", "What replaced `BaseModel.parse_obj()` in v2?", "exact_symbol", ["BaseModel.parse_obj"], "1.10", "2.0"),
    ("q_exact_03", "Is `BaseModel.copy()` still available in pydantic v2?", "exact_symbol", ["BaseModel.copy"], "1.10", "2.0"),
    ("q_exact_04", "What is the v2 equivalent of `BaseModel.construct()`?", "exact_symbol", ["BaseModel.construct"], "1.10", "2.0"),
    ("q_exact_05", "How do I replace `BaseModel.json()` when upgrading to v2?", "exact_symbol", ["BaseModel.json"], "1.10", "2.0"),
    ("q_exact_06", "Is the `@validator` decorator still recommended in pydantic v2?", "exact_symbol", ["@validator"], "1.10", "2.0"),
    ("q_exact_07", "What should I use instead of `@root_validator` in v2?", "exact_symbol", ["@root_validator"], "1.10", "2.0"),
    ("q_exact_08", "What replaced `BaseModel.update_forward_refs()` in v2?", "exact_symbol", ["BaseModel.update_forward_refs"], "1.10", "2.0"),

    # --- natural_language paraphrase (6), same underlying changes as above, no exact symbol named ---
    ("q_nl_01", "How do I turn a model instance into a plain dictionary now?", "natural_language", ["BaseModel.dict"], "1.10", "2.0"),
    ("q_nl_02", "What's the new way to build a model instance while skipping validation?", "natural_language", ["BaseModel.construct"], "1.10", "2.0"),
    ("q_nl_03", "How do I validate a plain dict into a model object now?", "natural_language", ["BaseModel.parse_obj"], "1.10", "2.0"),
    ("q_nl_04", "What's the current recommended way to write a field-level validator function?", "natural_language", ["@validator"], "1.10", "2.0"),
    ("q_nl_05", "How can I make a copy of a model instance in the new version?", "natural_language", ["BaseModel.copy"], "1.10", "2.0"),
    ("q_nl_06", "How do I resolve forward-referenced types after all my models are defined?", "natural_language", ["BaseModel.update_forward_refs"], "1.10", "2.0"),

    # --- single_hop migration for one specific change (8) ---
    ("q_single_01", "I'm on pydantic 1.10 and use `allow_mutation` in my model config -- what do I change for v2?", "single_hop", ["allow_mutation"], "1.10", "2.0"),
    ("q_single_02", "My code subclasses `GenericModel` for generic pydantic models -- how do I migrate this to v2?", "single_hop", ["generics.GenericModel"], "1.10", "2.0"),
    ("q_single_03", "I use `ConstrainedStr` for constrained string fields -- what's the v2 migration path?", "single_hop", ["ConstrainedStr"], "1.10", "2.0"),
    ("q_single_04", "My project uses `pydantic.stricturl` -- what do I need to change in v2?", "single_hop", ["stricturl"], "1.10", "2.0"),
    ("q_single_05", "I have type hints using `pydantic.NoneStr` -- how do I migrate to v2?", "single_hop", ["NoneStr"], "1.10", "2.0"),
    ("q_single_06", "I call `BaseModel.parse_file()` to load models from disk -- what's the v2 path?", "single_hop", ["BaseModel.parse_file"], "1.10", "2.0"),
    ("q_single_07", "My ORM integration relies on `BaseModel.from_orm()` -- how do I migrate it to v2?", "single_hop", ["BaseModel.from_orm"], "1.10", "2.0"),
    ("q_single_08", "I generate JSON schemas with `BaseModel.json_schema()` -- what changes in v2?", "single_hop", ["BaseModel.json_schema"], "1.10", "2.0"),

    # --- multi_hop migration spanning 2+ changes (6) ---
    ("q_multi_01", "A model class calls both `.dict()` and `.parse_obj()` -- what needs to change to migrate it to v2?", "multi_hop", ["BaseModel.dict", "BaseModel.parse_obj"], "1.10", "2.0"),
    ("q_multi_02", "My codebase uses both `@validator` and `@root_validator` extensively -- what's the full v2 upgrade path?", "multi_hop", ["@validator", "@root_validator"], "1.10", "2.0"),
    ("q_multi_03", "I have a settings class subclassing `BaseSettings` and other models calling `.dict()` -- what all changes for v2?", "multi_hop", ["BaseSettings", "BaseModel.dict"], "1.10", "2.0"),
    ("q_multi_04", "I use `GenericModel` for generics and `ConstrainedStr` for string constraints -- how do both migrate to v2?", "multi_hop", ["generics.GenericModel", "ConstrainedStr"], "1.10", "2.0"),
    ("q_multi_05", "My code imports `pydantic.color` and catches `pydantic.error_wrappers.ValidationError` -- what import paths change in v2?", "multi_hop", ["color", "error_wrappers.ValidationError"], "1.10", "2.0"),
    ("q_multi_06", "I call `.json()` and `.copy()` on models throughout my app -- what's the full v2 migration for both?", "multi_hop", ["BaseModel.json", "BaseModel.copy"], "1.10", "2.0"),

    # --- config_change (3 -- short of 5, see module docstring) ---
    ("q_config_01", "Is the `Config` inner class still used for model configuration in pydantic v2?", "config_change", ["Config"], "1.10", "2.0"),
    ("q_config_02", "I set `allow_mutation = False` on my model's `Config` -- what's the v2 equivalent?", "config_change", ["allow_mutation"], "1.10", "2.0"),
    ("q_config_03", "I pass extra keyword arguments to `Field()` for JSON schema metadata -- does that still work in v2?", "config_change", ["Field"], "1.10", "2.0"),

    # --- dependency_change (5) ---
    ("q_dep_01", "My project imports `BaseSettings` from `pydantic` -- what package do I need for v2?", "dependency_change", ["BaseSettings"], "1.10", "2.0"),
    ("q_dep_02", "I use `pydantic.color` types in my models -- what do I need to install for v2?", "dependency_change", ["color"], "1.10", "2.0"),
    ("q_dep_03", "My code catches `pydantic.error_wrappers.ValidationError` -- where does that live in v2?", "dependency_change", ["error_wrappers.ValidationError"], "1.10", "2.0"),
    ("q_dep_04", "I use `pydantic.utils.to_camel` for alias generation -- where did it move to in v2?", "dependency_change", ["utils.to_camel"], "1.10", "2.0"),
    ("q_dep_05", "My code calls `pydantic.tools.parse_obj_as` -- what's the v2 import path?", "dependency_change", ["tools.parse_obj_as"], "1.10", "2.0"),

    # --- behavioral_change (3 -- short of 5, see module docstring) ---
    ("q_behav_01", "Why do two models with the same field values no longer compare equal in v2 if they're different classes?", "behavioral_change", ["BaseModel.__eq__"], "1.10", "2.0"),
    ("q_behav_02", "My pydantic dataclass used to accept a tuple for a nested field and now raises a validation error in v2 -- why?", "behavioral_change", ["dataclasses"], "1.10", "2.0"),
    ("q_behav_03", "Why does `Field()` raise a validation error on extra keyword arguments now instead of just passing them through?", "behavioral_change", ["Field"], "1.10", "2.0"),

    # --- negative / no-change-needed (5), required_change_ids intentionally empty ---
    ("q_neg_01", "Does `BaseModel` still exist as the main way to define a schema in pydantic v2?", "negative", [], "1.10", "2.0"),
    ("q_neg_02", "Do I need to change how I define a required string field with `Field(...)` in pydantic v2?", "negative", [], "1.10", "2.0"),
    ("q_neg_03", "Is pydantic v2 still installed with `pip install pydantic`?", "negative", [], "1.10", "2.0"),
    ("q_neg_04", "Does defining nested `BaseModel` classes inside another model still work the same way in v2?", "negative", [], "1.10", "2.0"),
    ("q_neg_05", "Do `Enum` field definitions need any changes to work with pydantic v2?", "negative", [], "1.10", "2.0"),

    # --- ambiguous / alias (4) ---
    ("q_amb_01", "What happened to `parse` in pydantic v2?", "ambiguous_alias", ["BaseModel.parse_obj", "BaseModel.parse_raw", "BaseModel.parse_file"], "1.10", "2.0"),
    ("q_amb_02", "Where did `validator` go in pydantic v2?", "ambiguous_alias", ["@validator"], "1.10", "2.0"),
    ("q_amb_03", "What's the relationship between `root_validator` and `model_validator`?", "ambiguous_alias", ["@root_validator"], "1.10", "2.0"),
    ("q_amb_04", "Is `Config` still a thing in pydantic v2?", "ambiguous_alias", ["Config"], "1.10", "2.0"),
]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    symbol_to_change_id: dict[str, str] = {}
    for row in conn.execute("SELECT change_id, symbol_name FROM change_records"):
        symbol_to_change_id[row["symbol_name"]] = row["change_id"]

    change_to_evidence_ids: dict[str, list[str]] = {}
    for row in conn.execute("SELECT change_id, evidence_id FROM evidence_links"):
        change_to_evidence_ids.setdefault(row["change_id"], []).append(row["evidence_id"])

    gold = []
    missing_symbols = set()

    for query_id, query_text, query_type, symbols, from_version, to_version in GOLD_QUERIES:
        change_ids = []
        evidence_ids: list[str] = []
        for symbol in symbols:
            change_id = symbol_to_change_id.get(symbol)
            if change_id is None:
                missing_symbols.add(symbol)
                continue
            change_ids.append(change_id)
            evidence_ids.extend(change_to_evidence_ids.get(change_id, []))

        gold.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "query_type": query_type,
                "from_version": from_version,
                "to_version": to_version,
                "required_change_ids": change_ids,
                "relevant_evidence_ids": evidence_ids,
            }
        )

    if missing_symbols:
        raise RuntimeError(f"Symbols referenced by gold queries not found in change_records: {sorted(missing_symbols)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(gold, indent=2), encoding="utf-8")

    print(f"Wrote {len(gold)} gold queries to {OUTPUT_PATH}")
    by_type: dict[str, int] = {}
    for q in gold:
        by_type[q["query_type"]] = by_type.get(q["query_type"], 0) + 1
    for query_type, count in sorted(by_type.items()):
        print(f"  {query_type}: {count}")


if __name__ == "__main__":
    main()
