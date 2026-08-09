import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import run_pipeline

"""
Generate data/gold/pydantic_gold_queries.json against the real
change_id/evidence_id/chunk_id values produced by the real pipeline.
Queries below reference symbol names and stability-fact text (looked up
here), not raw hash ids, so a corpus rebuild can't silently desync the
gold set from typos.

Stage 8A taxonomy (48 total): exact_symbol 8, natural_language 6,
single_change 8, multi_change 6, config_change 3, dependency_change 5,
behavioral_change 3, negative 5, underspecified_symbol 1, legacy_symbol 3.

Renamed from Stage 7's multi_hop/single_hop: this benchmark covers one
version transition (1.10.x -> 2.x) and never exercises a version-path
chain (v2->v3->v4->v5), so "multi-hop" overstated what's actually tested
-- these queries combine multiple co-occurring changes within the same
transition, not multiple transitions. ambiguous_alias split into
underspecified_symbol (q_amb_01 -- a single bare term matching several
real symbols, genuinely under-specified) and legacy_symbol (q_amb_02/03/04
-- asking about one specific old name, not actually ambiguous).

config_change and behavioral_change are short of the suggested 5 each --
documented honestly rather than padded: bare, non-dotted config-setting
names (`orm_mode`, `schema_extra`, `Optional`, etc.) don't survive
symbol detection by design (see symbol_normalization.py -- a bare
backtick word is treated as a parameter name, not a symbol), so most of
the real Config-setting renames in migration_guide.md never became
UnresolvedChange claims at all. This is a real Level 1 extraction-
coverage finding, not a gold-set-authoring shortcut.

Stage 8A.1/8A.2: added `evaluation_scope`, three values:
- "change_retrieval" (42 queries): the core Dense/BM25/Hybrid Recall@K
  aggregate.
- "stability" (5 queries, the negatives): required_change_ids is always
  vacuously empty, so change-level Recall@K is trivially 1.0 regardless
  of retrieval quality -- not a meaningful signal for the same aggregate,
  reported separately.
- "query_planner" (1 query, q_amb_01): its required_change_ids set (3 of
  pydantic's several parse_* symbols) is itself a human editorial choice
  about what a bare, underspecified query "should" mean -- there is no
  single correct retrieval target to score against. Scoring it in the
  core aggregate would penalize the retriever for not answering a
  question that doesn't have one gold interpretation; it belongs to a
  future query-understanding/disambiguation benchmark instead.

run_pydantic_benchmark.py filters to "change_retrieval" for the core
aggregate/per-type/CSV tables and reports the other two scopes separately.

GOLD_QUERIES entries: (query_id, query_text, query_type, symbols,
from_version, to_version, evaluation_scope). symbols is a list of real
symbol_name values; required_change_ids/relevant_evidence_ids are
resolved from it.

NEGATIVE_QUERIES entries: (query_id, query_text, from_version, to_version,
stability_fact_text) -- stability_fact_text must match a chunk's text
exactly (from data/corpus/pydantic/concepts.md's "Stable in v2" section);
resolved to a chunk_id, not an evidence_id (stability facts don't go
through Level 1 extraction -- see Stage 8A feasibility note in
docs/entity-aggregation-log.md).
"""

DB_PATH = Path("data/entities.db")
OUTPUT_PATH = Path("data/gold/pydantic_gold_queries.json")

# Stage 8A.2 §3: gold set identity/versioning metadata. status/source_commit
# are filled in only at the actual freeze moment (a separate, explicit human
# action -- see docs/entity-aggregation-log.md) -- this script never sets them
# to "frozen" itself. review_revision bumps by hand each time a human review
# round produces corrections (this is round 3: Stage 8A -> 8A.1 -> 8A.2).
GOLD_METADATA = {
    "name": "Pydantic Gold Set v1",
    "migration_scope": "1.10.x -> 2.x",
    "review_revision": 3,
    "status": "pending_freeze",
    "source_commit": None,
}

GOLD_QUERIES = [
    # --- exact_symbol (8) ---
    ("q_exact_01", "What happened to `BaseModel.dict()` in pydantic v2?", "exact_symbol", ["BaseModel.dict"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_02", "What replaced `BaseModel.parse_obj()` in v2?", "exact_symbol", ["BaseModel.parse_obj"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_03", "Is `BaseModel.copy()` still available in pydantic v2?", "exact_symbol", ["BaseModel.copy"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_04", "What is the v2 equivalent of `BaseModel.construct()`?", "exact_symbol", ["BaseModel.construct"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_05", "How do I replace `BaseModel.json()` when upgrading to v2?", "exact_symbol", ["BaseModel.json"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_06", "Is the `@validator` decorator still recommended in pydantic v2?", "exact_symbol", ["@validator"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_07", "What should I use instead of `@root_validator` in v2?", "exact_symbol", ["@root_validator"], "1.10", "2.0", "change_retrieval"),
    ("q_exact_08", "What replaced `BaseModel.update_forward_refs()` in v2?", "exact_symbol", ["BaseModel.update_forward_refs"], "1.10", "2.0", "change_retrieval"),

    # --- natural_language paraphrase (6), same underlying changes as above, no exact symbol named ---
    ("q_nl_01", "How do I turn a model instance into a plain dictionary now?", "natural_language", ["BaseModel.dict"], "1.10", "2.0", "change_retrieval"),
    ("q_nl_02", "What's the new way to build a model instance while skipping validation?", "natural_language", ["BaseModel.construct"], "1.10", "2.0", "change_retrieval"),
    ("q_nl_03", "How do I validate a plain dict into a model object now?", "natural_language", ["BaseModel.parse_obj"], "1.10", "2.0", "change_retrieval"),
    ("q_nl_04", "What's the current recommended way to write a field-level validator function?", "natural_language", ["@validator"], "1.10", "2.0", "change_retrieval"),
    ("q_nl_05", "How can I make a copy of a model instance in the new version?", "natural_language", ["BaseModel.copy"], "1.10", "2.0", "change_retrieval"),
    ("q_nl_06", "How do I resolve forward-referenced types after all my models are defined?", "natural_language", ["BaseModel.update_forward_refs"], "1.10", "2.0", "change_retrieval"),

    # --- single_change: one specific change within the 1.10->2.0 transition (8) ---
    ("q_single_01", "I'm on pydantic 1.10 and use `allow_mutation` in my model config -- what do I change for v2?", "single_change", ["allow_mutation"], "1.10", "2.0", "change_retrieval"),
    ("q_single_02", "My code subclasses `GenericModel` for generic pydantic models -- how do I migrate this to v2?", "single_change", ["generics.GenericModel"], "1.10", "2.0", "change_retrieval"),
    ("q_single_03", "I use `ConstrainedStr` for constrained string fields -- what's the v2 migration path?", "single_change", ["ConstrainedStr"], "1.10", "2.0", "change_retrieval"),
    # stricturl: official migration guide lists no 1:1 replacement -- query
    # asks only whether it was removed, not "what do I change", so the
    # gold doesn't imply an action that isn't verified (Stage 8A.1 §2).
    ("q_single_04", "Was `pydantic.stricturl` removed in v2?", "single_change", ["stricturl"], "1.10", "2.0", "change_retrieval"),
    ("q_single_05", "I have type hints using `pydantic.NoneStr` -- how do I migrate to v2?", "single_change", ["NoneStr"], "1.10", "2.0", "change_retrieval"),
    ("q_single_06", "I call `BaseModel.parse_file()` to load models from disk -- what's the v2 path?", "single_change", ["BaseModel.parse_file"], "1.10", "2.0", "change_retrieval"),
    ("q_single_07", "My ORM integration relies on `BaseModel.from_orm()` -- how do I migrate it to v2?", "single_change", ["BaseModel.from_orm"], "1.10", "2.0", "change_retrieval"),
    ("q_single_08", "I generate JSON schemas with `BaseModel.schema()`. What should I use in v2?", "single_change", ["BaseModel.schema"], "1.10", "2.0", "change_retrieval"),

    # --- multi_change: 2+ co-occurring changes within the same 1.10->2.0 transition (6) ---
    # NOT true version-path multi-hop (that needs a corpus spanning multiple
    # sequential transitions, e.g. v2->v3->v4->v5 -- out of scope here).
    ("q_multi_01", "A model class calls both `.dict()` and `.parse_obj()` -- what needs to change to migrate it to v2?", "multi_change", ["BaseModel.dict", "BaseModel.parse_obj"], "1.10", "2.0", "change_retrieval"),
    ("q_multi_02", "My codebase uses both `@validator` and `@root_validator` extensively -- what's the full v2 upgrade path?", "multi_change", ["@validator", "@root_validator"], "1.10", "2.0", "change_retrieval"),
    ("q_multi_03", "I have a settings class subclassing `BaseSettings` and other models calling `.dict()` -- what all changes for v2?", "multi_change", ["BaseSettings", "BaseModel.dict"], "1.10", "2.0", "change_retrieval"),
    ("q_multi_04", "I use `GenericModel` for generics and `ConstrainedStr` for string constraints -- how do both migrate to v2?", "multi_change", ["generics.GenericModel", "ConstrainedStr"], "1.10", "2.0", "change_retrieval"),
    ("q_multi_05", "My code imports `pydantic.color` and catches `pydantic.error_wrappers.ValidationError` -- what import paths change in v2?", "multi_change", ["color", "error_wrappers.ValidationError"], "1.10", "2.0", "change_retrieval"),
    ("q_multi_06", "I call `.json()` and `.copy()` on models throughout my app -- what's the full v2 migration for both?", "multi_change", ["BaseModel.json", "BaseModel.copy"], "1.10", "2.0", "change_retrieval"),

    # --- config_change (3 -- short of 5, see module docstring) ---
    ("q_config_01", "Is the `Config` inner class still used for model configuration in pydantic v2?", "config_change", ["Config"], "1.10", "2.0", "change_retrieval"),
    ("q_config_02", "I set `allow_mutation = False` on my model's `Config` -- what's the v2 equivalent?", "config_change", ["allow_mutation"], "1.10", "2.0", "change_retrieval"),
    ("q_config_03", "I pass extra keyword arguments to `Field()` for JSON schema metadata -- does that still work in v2?", "config_change", ["Field"], "1.10", "2.0", "change_retrieval"),

    # --- dependency_change (5) ---
    ("q_dep_01", "My project imports `BaseSettings` from `pydantic` -- what package do I need for v2?", "dependency_change", ["BaseSettings"], "1.10", "2.0", "change_retrieval"),
    ("q_dep_02", "I use `pydantic.color` types in my models -- what do I need to install for v2?", "dependency_change", ["color"], "1.10", "2.0", "change_retrieval"),
    ("q_dep_03", "My code catches `pydantic.error_wrappers.ValidationError` -- where does that live in v2?", "dependency_change", ["error_wrappers.ValidationError"], "1.10", "2.0", "change_retrieval"),
    ("q_dep_04", "I use `pydantic.utils.to_camel` -- where did it move in v2?", "dependency_change", ["utils.to_camel"], "1.10", "2.0", "change_retrieval"),
    ("q_dep_05", "How should I replace `pydantic.tools.parse_obj_as` in v2?", "dependency_change", ["tools.parse_obj_as"], "1.10", "2.0", "change_retrieval"),

    # --- behavioral_change (3 -- short of 5, see module docstring) ---
    # q_behav_01: narrowed to non-generic models -- the equality rule for
    # generic models allows some same-origin cases, so "exact same type,
    # unconditionally" overstated the real rule (Stage 8A.1 §3).
    ("q_behav_01", "Why do two non-generic models of different model types no longer compare equal in v2 even with matching field values?", "behavioral_change", ["BaseModel.__eq__"], "1.10", "2.0", "change_retrieval"),
    ("q_behav_02", "My pydantic dataclass used to accept a tuple for a nested field and now raises a validation error in v2 -- why?", "behavioral_change", ["dataclasses"], "1.10", "2.0", "change_retrieval"),
    # q_behav_03: softened -- evidence supports "unsupported, use
    # json_schema_extra instead", not a specific exception type
    # (Stage 8A.1 §3).
    ("q_behav_03", "Why don't arbitrary extra kwargs on `Field()` work for JSON Schema metadata in v2?", "behavioral_change", ["Field"], "1.10", "2.0", "change_retrieval"),

    # --- underspecified_symbol (1): a single bare term matching multiple real symbols ---
    # evaluation_scope=query_planner: the required-change set here is an
    # editorial choice about what "parse" should mean, not a single
    # retrieval ground truth -- excluded from the core Recall@K aggregate.
    ("q_amb_01", "What happened to `parse` in pydantic v2?", "underspecified_symbol", ["BaseModel.parse_obj", "BaseModel.parse_raw", "BaseModel.parse_file"], "1.10", "2.0", "query_planner"),

    # --- legacy_symbol (3): asks about one specific old name, not actually ambiguous ---
    ("q_amb_02", "Where did `validator` go in pydantic v2?", "legacy_symbol", ["@validator"], "1.10", "2.0", "change_retrieval"),
    ("q_amb_03", "What's the relationship between `root_validator` and `model_validator`?", "legacy_symbol", ["@root_validator"], "1.10", "2.0", "change_retrieval"),
    ("q_amb_04", "Is `Config` still a thing in pydantic v2?", "legacy_symbol", ["Config"], "1.10", "2.0", "change_retrieval"),
]

# (query_id, query_text, from_version, to_version, stability_fact_text)
# stability_fact_text must match a "Stable in v2" bullet in concepts.md exactly.
NEGATIVE_QUERIES = [
    # Stage 8A.2 §4: tightened to mirror the stability evidence's own
    # wording closely ("primary way" / "behave the same way"), rather than
    # a looser paraphrase ("still exist as the main way" / "still work the
    # same way") that claimed slightly more than the evidence states.
    (
        "q_neg_01",
        "Is subclassing `BaseModel` still the primary way to define a schema in pydantic v2?",
        "1.10", "2.0",
        "Subclassing `BaseModel` remains the primary way to define a schema in pydantic v2, the same as in v1.",
    ),
    (
        "q_neg_02",
        "Does a field given an explicit default value, such as `Field(default=None)`, still behave the same way in pydantic v2?",
        "1.10", "2.0",
        "A field given an explicit default value, such as `Field(default=None)`, continues to behave the same way in v2; only fields with no explicit default changed.",
    ),
    (
        "q_neg_03",
        "Is pydantic v2 still installed with `pip install pydantic`?",
        "1.10", "2.0",
        "The core `pydantic` package is still installed with `pip install pydantic` in v2 -- only optional add-ons like settings management and extra types moved to separate packages.",
    ),
    (
        "q_neg_04",
        "Can a `BaseModel` field still be typed as another `BaseModel` subclass (nested model composition) in pydantic v2?",
        "1.10", "2.0",
        "Nested model composition, typing a field as another `BaseModel` subclass, is still supported in v2.",
    ),
    # q_neg_05 replaced (Stage 8A.1 §4): the old query ("is custom
    # validation still supported?") was entangled with a real API
    # migration (@validator -> @field_validator) via its own stability
    # evidence -- "capability preserved, API migration required" is not
    # "no migration change" and would have polluted negative-set scoring.
    # This one is a clean, narrow, unconflated claim.
    (
        "q_neg_05",
        "Do I still access individual field values as plain attributes (e.g. `model.field_name`) in pydantic v2?",
        "1.10", "2.0",
        "Accessing individual field values as plain attributes, e.g. `model.field_name`, is unchanged in pydantic v2.",
    ),
]


def main() -> None:
    chunks, conn, _stats = run_pipeline()
    conn.row_factory = sqlite3.Row

    symbol_to_change_id: dict[str, str] = {}
    for row in conn.execute("SELECT change_id, symbol_name FROM change_records"):
        symbol_to_change_id[row["symbol_name"]] = row["change_id"]

    change_to_evidence_ids: dict[str, list[str]] = {}
    for row in conn.execute("SELECT change_id, evidence_id FROM evidence_links"):
        change_to_evidence_ids.setdefault(row["change_id"], []).append(row["evidence_id"])

    text_to_chunk_id: dict[str, str] = {c.text.strip(): c.chunk_id for c in chunks}

    gold = []
    missing_symbols = set()
    missing_stability_facts = set()

    for query_id, query_text, query_type, symbols, from_version, to_version, evaluation_scope in GOLD_QUERIES:
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
                "stability_evidence_ids": [],
                "evaluation_scope": evaluation_scope,
            }
        )

    for query_id, query_text, from_version, to_version, stability_fact_text in NEGATIVE_QUERIES:
        chunk_id = text_to_chunk_id.get(stability_fact_text.strip())
        if chunk_id is None:
            missing_stability_facts.add(stability_fact_text)

        gold.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "query_type": "negative",
                "from_version": from_version,
                "to_version": to_version,
                "required_change_ids": [],
                "relevant_evidence_ids": [],
                "stability_evidence_ids": [chunk_id] if chunk_id else [],
                "evaluation_scope": "stability",
            }
        )

    if missing_symbols:
        raise RuntimeError(f"Symbols referenced by gold queries not found in change_records: {sorted(missing_symbols)}")
    if missing_stability_facts:
        raise RuntimeError(f"Stability facts not found as an exact chunk match: {sorted(missing_stability_facts)}")

    output = {"metadata": GOLD_METADATA, "queries": gold}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {len(gold)} gold queries to {OUTPUT_PATH} ({GOLD_METADATA['name']}, review_revision={GOLD_METADATA['review_revision']})")
    by_type: dict[str, int] = {}
    for q in gold:
        by_type[q["query_type"]] = by_type.get(q["query_type"], 0) + 1
    for query_type, count in sorted(by_type.items()):
        print(f"  {query_type}: {count}")

    by_scope: dict[str, int] = {}
    for q in gold:
        by_scope[q["evaluation_scope"]] = by_scope.get(q["evaluation_scope"], 0) + 1
    for scope, count in sorted(by_scope.items()):
        print(f"  evaluation_scope={scope}: {count}")


if __name__ == "__main__":
    main()
