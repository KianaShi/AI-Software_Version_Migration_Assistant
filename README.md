# Software Version Migration Assistant

A version-aware RAG system for identifying software breaking changes, linking evidence across documentation and code sources, and generating grounded migration guidance.

The project is being redesigned from a general-purpose RAG prototype into a software migration assistant focused on a specific challenge:

> Software changes are rarely documented in one place.

A single breaking change may appear across release notes, migration guides, pull requests, issues, code diffs, and API documentation. These sources may use different wording, refer to different versions, or describe different aspects of the same underlying change.

The goal of this project is to build a retrieval system that can identify those relationships without incorrectly merging unrelated changes.

---

## Why This Problem Needs More Than Basic RAG

A standard RAG pipeline often looks like:

```text
Question
→ Vector Search
→ Top-k Chunks
→ LLM Answer
```

That is not sufficient for software migration.

For example, upgrading a library from `v2` to `v5` may require understanding several intermediate transitions:

```text
v2 → v3
v3 → v4
v4 → v5
```

The same API may also appear in:

* an official migration guide explaining what users should do,
* a release note describing what changed,
* a pull request showing how the implementation changed,
* an issue describing a real migration failure.

These documents should not be treated as four independent answers.

They may instead be four pieces of evidence describing the same software change.

At the same time, aggressively grouping similar documents is dangerous: two changes may involve the same symbol or parameter while representing completely different modifications.

This project therefore separates:

```text
Evidence retrieval
        ↓
Change extraction
        ↓
Entity resolution
        ↓
Evidence aggregation
        ↓
Migration reasoning
```

---

# Current Architecture

```text
Raw Sources
    │
    ↓
Level 1 Change Extraction
    │
    │   produces
    ↓
UnresolvedChange + Evidence
    │
    ↓
Candidate Blocking
    │
    ↓
Hard Constraints
    │
    ↓
Pairwise Evidence Scoring
    │
    ↓
Precision-First Linker
    │
    ↓
ChangeRecord
    │
    └── EvidenceLink[]
```

The current implementation covers Level 1 extraction, entity resolution / evidence aggregation, and a Retrieval v1 baseline (dense + sparse + hybrid + version filtering), benchmarked end to end against a real pydantic 1.10.x → 2.x migration corpus. See [Benchmark Results](#benchmark-results-stage-7) below.

Reranking, Late Chunking, query decomposition, and LLM-based extraction fallback are the next candidates, prioritized by what the benchmark's failure analysis actually shows is worth adding (see that section).

---

# Entity and Evidence Model

The project distinguishes between a **change event** and the **evidence describing that event**.

For example:

```text
ChangeRecord
FooClient signature change in v5
        │
        ├── Release Note
        ├── Migration Guide
        ├── Pull Request
        └── Code Diff
```

Each source remains independently traceable.

The system never treats an evidence document itself as the canonical change identifier.

Core entities include:

* `Symbol`
* `ChangeAttributes`
* `UnresolvedChange`
* `ChangeRecord`
* `Evidence`
* `EvidenceLink`
* `CannotLinkConstraint`

Entity state is stored in a local SQLite repository.

---

# Precision-First Evidence Aggregation

Incorrectly merging two unrelated changes can be more dangerous than failing to merge two related ones.

A false split may reduce evidence completeness.

A false merge can contaminate an evidence bundle and cause the downstream model to produce an incorrect migration recommendation.

For that reason, the current aggregation layer is intentionally **precision-first**.

The linker does not automatically select a candidate when:

* multiple plausible change records remain,
* evidence is ambiguous,
* a hard cannot-link rule is triggered,
* confidence does not meet the required threshold.

Ambiguous evidence remains unresolved rather than being forced into an existing change bundle.

---

## Candidate Blocking

`src/aggregation/blocking.py`

Blocking reduces the candidate search space using structured information such as:

* package
* canonical symbol
* version compatibility

Blocking is intentionally separate from semantic similarity.

The purpose of this stage is candidate generation, not final entity resolution.

---

## Hard Constraints

`src/aggregation/constraints.py`

Hard cannot-link rules use deterministic structured comparisons.

Semantic embeddings are not used inside the constraint layer.

Each constraint returns an explainable result:

```python
ConstraintResult(
    allowed=False,
    reason="INCOMPATIBLE_CHANGE_TYPES",
    detail="..."
)
```

This makes false splits traceable to the exact rule that rejected a link.

Change-type compatibility is controlled through an explicit whitelist.

The default behavior is conservative: incompatible change types are not automatically treated as the same software change.

---

## Pairwise Evidence Scoring

`src/aggregation/pairwise.py`

Evidence pairs that pass blocking and hard constraints are evaluated using multiple signals.

The scorer returns both the final score and the individual contributing signals:

```python
PairwiseScore(
    total=...,
    signals={
        "symbol_match": ...,
        "version_compatibility": ...,
        "change_type_match": ...,
        "semantic_similarity": ...
    }
)
```

Semantic similarity is therefore one signal among several rather than the sole entity-resolution criterion.

All weights and thresholds are centralized in:

```text
src/aggregation/config.py
```

This allows the scoring model to be calibrated later using a human-verified linkage dataset rather than relying on hard-coded values distributed throughout the implementation.

---

# Link Confidence and Provenance

Evidence relationships are not treated as equally reliable.

The system distinguishes between relationships such as:

```text
Explicit source relationship
        ↓
High-confidence inferred relationship
        ↓
Ambiguous candidate
```

Internally, links retain:

* link method
* confidence
* provenance
* resolution status

The presentation layer intentionally does not expose raw internal confidence scores as calibrated probabilities.

Instead, `src/presentation/confidence_view.py` maps internal states to user-facing descriptions such as:

* official / explicit relationship
* system-linked evidence
* possible related evidence

This avoids implying that an internal similarity score represents a literal probability of correctness.

---

# Why Aggregation Is Separate From Extraction

The project intentionally separates two questions.

### Level 1 Extraction

> What change does this piece of evidence claim occurred?

Expected output:

```text
UnresolvedChange
+
Evidence
```

### Entity Resolution

> Which software change event does this evidence belong to?

Expected output:

```text
ChangeRecord
+
EvidenceLink
```

This separation prevents the extraction layer from silently making entity-resolution decisions.

Level 1 extraction (`src/extraction/`) is implemented and deterministic-first: regex/keyword rules handle explicit version numbers, symbol references, and a fixed vocabulary of change verbs; an `LLMExtractor` interface exists as a documented seam for a future structured-LLM fallback, but nothing calls a live model yet. It is intentionally being kept out until the retrieval baseline below establishes what a fallback would actually need to improve.

---

# Testing

The project currently includes **140 passing tests** across entity models, candidate blocking, hard cannot-link constraints, pairwise scoring, precision-first linking, Level 1 extraction (including deliberately adversarial "don't over-extract" cases), source-aware chunking, dense/sparse/hybrid retrieval, version-interval filtering, and the evaluation harness.

Several tests intentionally focus on difficult negative cases: evidence that shares a symbol or similar language but should **not** be merged (Level 2), and statements that merely mention a symbol without describing a change (Level 1).

There are also five pre-existing failures in legacy `retriever.py`/`vector_store.py` tests caused by historical interface mismatches, predating this work. They're intentionally being left alone: those two modules are expected to be replaced by a Hybrid Retrieval / Qdrant layer, so realigning tests to an interface likely to be rewritten has low value. They'll be revisited in their own commit once that layer's fate is decided.

---

# Benchmark Results (Stage 7)

A deterministic baseline was frozen (chunking → dense/sparse/hybrid → Recall@K/MRR/nDCG) and benchmarked *before* considering an LLM extraction fallback, reranker, or Late Chunking -- adding any of those first would make it impossible to tell whether a later improvement came from retrieval or from more/better-extracted evidence.

**Corpus**: pydantic 1.10.x → 2.x only (no internal 2.x churn), grounded in the real [official migration guide](https://docs.pydantic.dev/latest/migration/) -- original short-form notes, not copied verbatim, covering BaseModel method renames, config renames, field/validator changes, generics/dataclass changes, moved/dependency-split symbols, and behavior changes. Run through the actual Level 1 → Level 2 pipeline (no hand-invented ids): 3 source documents → 70 chunks → 33 extracted `UnresolvedChange` claims → 26 resolved `ChangeRecord`s (6 deduplicated across independent migration-guide/release-note evidence via real pairwise resolution, 0 cannot-link vetoes needed).

**Gold set**: 48 human-authored queries (`data/gold/pydantic_gold_queries.json`) across 9 taxonomy buckets (exact_symbol, natural_language paraphrase, single_hop, multi_hop, config_change, dependency_change, behavioral_change, negative, ambiguous_alias), each carrying real `required_change_ids` and `relevant_evidence_ids` resolved from the pipeline output above, not placeholders. `config_change` (3) and `behavioral_change` (3) are short of the target 5 -- see the Known Limitations note below, not padded to hit a number.

## Aggregate (change-level, `required_change_ids`)

| Retrieval | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|
| Dense | 0.927 | 0.948 | 0.796 | 0.794 |
| BM25 (sparse) | 0.844 | 0.844 | 0.694 | 0.702 |
| Hybrid (RRF) | **0.958** | **0.958** | **0.807** | **0.819** |
| Hybrid + version filter | 0.938 | 0.938 | 0.786 | 0.798 |

## Per query type (Recall@5)

| Query type | Dense | BM25 | Hybrid |
|---|---|---|---|
| exact_symbol | 1.000 | 1.000 | 1.000 |
| natural_language | 0.833 | **0.167** | 0.833 |
| single_hop | 1.000 | 1.000 | 1.000 |
| multi_hop | 0.917 | 0.917 | 1.000 |
| config_change | 1.000 | 0.667 | 1.000 |
| dependency_change | 1.000 | 1.000 | 1.000 |
| behavioral_change | 1.000 | 1.000 | 1.000 |
| ambiguous_alias | 0.500 | 0.750 | 0.750 |
| negative | 1.000 | 1.000 | 1.000 |

The `natural_language` row is the headline result: sparse retrieval was far weaker on paraphrased migration questions with no exact symbol name (BM25 has no term to match on), while dense held up -- and hybrid lost nothing relative to dense's better score. Full per-type table for all four modes: `data/benchmark/per_query_type_results.csv`. Full per-query detail: `data/benchmark/per_query_results.csv`.

## Failure analysis

Of 43 non-negative queries, only 2 fail under all three retrieval modes at Recall@5 (down from 18 before a chunking bug described below was fixed):

- **`q_nl_02`** ("What's the new way to build a model instance while skipping validation?", expecting `model_construct`) -- the paraphrase is distant enough from the corpus wording that no retriever surfaces the right chunk in the top 5. A **query wording problem** more than a retrieval-index problem; the fact is in the corpus and individually addressable, it just never scores high enough. Candidate fix: reranker.
- **`q_amb_01`** ("What happened to `parse` in pydantic v2?", expecting 3 of pydantic's several `parse_*` symbols) -- a single bare, highly ambiguous term retrieves other superficially-related "removed"/"moved" facts instead. A **query wording / disambiguation problem**. Candidate fix: query decomposition or a clarifying-question step, not a bigger index.

Two more findings came directly from running this benchmark against real data, both already fixed (with regression tests) before these numbers were produced, not silently patched:

- **Chunking granularity bug** -- `migration_guide`/`official_docs` chunking bundled every bullet under a heading into one chunk (e.g. all 11 `BaseModel` method renames as one chunk's embedding), diluting the signal for any single fact. Change-level Recall@5 across the board before the fix: dense 0.604, sparse 0.542, hybrid 0.635; after switching to per-bullet chunking whenever a section is itemized: 0.927 / 0.844 / 0.958. This is the single largest lever pulled in this stage -- bigger than the retrieval algorithm choice itself.
- **Version-interval comparison bug** -- `(2,) < (2, 0, 0)` under plain tuple comparison, so a bare "v2" query and a "2.0.0"-tagged chunk were wrongly treated as non-overlapping, collapsing `hybrid_version_filtered` to Recall@5 = 0.208. Fixed by padding tuples to equal length before comparing (`src/retrieval/version_filter.py`).
- A third bug (`replacement_symbol`/`parameters` silently dropped when `linker.py` originated a new `ChangeRecord`) was also caught by running real extracted data through aggregation, unrelated to retrieval scoring but would have corrupted `ChangeRecord.replacement_symbol` for every real REPLACEMENT/MOVED change.

**Known limitation, not fixed this pass**: `config_change` and `behavioral_change` gold buckets are thinner than intended (3 queries each, not 5) because several real config-setting renames (`orm_mode`, `schema_extra`, bare `Optional`, etc.) never became `UnresolvedChange` claims at all -- `symbol_normalization.py` deliberately excludes bare, non-dotted backtick words from symbol detection (to avoid misreading parameter names like `` `timeout` `` as symbols), which also excludes bare config-key names. This is a real Level 1 extraction-coverage gap, not a retrieval failure, and not silently patched by loosening the symbol detector (that would risk exactly the false-symbol-detection failure mode a regression test already guards against). Worth a follow-up if Config-setting-rename coverage matters for a future corpus.

**Version filter ablation caveat**: this corpus is scoped to a single target version (2.0.0), so `hybrid_version_filtered` has little room to differ from `hybrid` here (0.938 vs 0.958) -- the filter can only meaningfully help/hurt on a corpus spanning multiple versions with genuinely conflicting content, which this first corpus doesn't exercise.

Reproduce: `python -m scripts.build_pydantic_benchmark_corpus` then `python -m scripts.run_pydantic_benchmark` (rebuilds `data/entities.db` and both indices from scratch each run; regenerate the gold set itself with `python -m scripts.generate_pydantic_gold_set` if the corpus text changes).

---

# Planned Retrieval Architecture

The long-term system is intended to use a version-aware retrieval workflow:

```text
User Query + Repository
        ↓
Dependency / Code Analysis
        ↓
Migration Path Detection
        ↓
Budgeted Query Decomposition
        ↓
Hybrid Retrieval
        ↓
Reranking
        ↓
Evidence Resolution
        ↓
Coverage / Conflict Checking
        ↓
Adaptive Retrieval if Needed
        ↓
Grounded Migration Recommendation
        ↓
Citations
```

Retrieval work status:

* [x] source-aware document parsing
* [x] version metadata
* [x] dense + sparse hybrid retrieval (v1 baseline, benchmarked -- see above)
* [x] version-aware filtering
* [ ] Late Chunking experiments for documentation (ablation target against the v1 chunking baseline)
* [ ] Tree-sitter parsing for source code
* [ ] reranking
* [ ] multi-hop migration queries (multi_hop is a benchmarked gold-set category already; dedicated query decomposition is still planned)
* [ ] adaptive evidence retrieval

The remaining unchecked components are still roadmap, not completed features.

---

# Evaluation Plan

Evaluation will be performed separately at each layer rather than using a single end-to-end score.

## Entity Resolution

Planned metrics:

* Link Precision
* Link Recall
* False Merge Rate
* False Split Rate
* Bundle Purity

False Merge Rate and False Split Rate will be tracked separately because their downstream costs are asymmetric.

## Retrieval

* [x] Recall@K, MRR, nDCG -- implemented and run for real (see [Benchmark Results](#benchmark-results-stage-7))
* [ ] Migration Chain Recall -- the evaluation harness's metric functions are already item-id-agnostic and `required_change_ids` is already the right shape for this; it's a new metric function over the same resolved id lists, not a re-annotation of the gold set
* [ ] affected-symbol coverage

## Generation

Planned metrics:

* faithfulness
* migration completeness
* citation correctness
* version correctness
* unsupported critical claim rate

## End-to-End

Later experiments will test whether generated migration recommendations can be applied to controlled repositories and validated using executable tests.

---

# Project Status

### Completed

* [x] Removed Shakespeare-specific prototype code and corpus
* [x] Core entity schema
* [x] SQLite entity repository
* [x] Candidate blocking
* [x] Deterministic cannot-link constraints
* [x] Pairwise multi-signal scoring
* [x] Precision-first evidence linker
* [x] Explainable score breakdown
* [x] Confidence/provenance presentation layer
* [x] Entity/aggregation test suite
* [x] Level 1 source ingestion (release_note / migration_guide / official_docs / github_pr_issue adapters)
* [x] Deterministic-first change extraction
* [x] Symbol normalization
* [x] Version normalization (incl. interval overlap, not string equality)
* [x] Extraction provenance and confidence (EXPLICIT / INFERRED)
* [x] Source-aware chunking (per-bullet when itemized, per-heading-section when prose)
* [x] Dense + sparse (BM25) + hybrid (RRF) retrieval baseline
* [x] Version-aware post-retrieval filtering
* [x] Recall@K / MRR / nDCG evaluation harness
* [x] Real benchmark corpus + 48-query human-authored gold set (pydantic 1.10.x → 2.x)
* [x] Dense vs. sparse vs. hybrid vs. hybrid+version-filter benchmark, per-query-type slicing, failure analysis

### In Progress / Next

* [ ] Reranker (candidate: fixes cases where the right chunk is indexed but scores too low, e.g. `q_nl_02`)
* [ ] Query decomposition / disambiguation (candidate: fixes ambiguous short-term queries, e.g. `q_amb_01`)
* [ ] LLM-based extraction fallback (interface already exists in `llm_fallback.py`; not wired to a live model -- benchmark above is what will justify whether/where it's worth it)
* [ ] Migration Chain Recall metric
* [ ] Config-setting-rename extraction coverage (bare non-dotted symbol names currently excluded by design -- see Benchmark Results known limitations)

### Planned

* [ ] Late Chunking benchmark (ablate against the chunking baseline above)
* [ ] Tree-sitter code parsing
* [ ] Reranking
* [ ] Migration-path query decomposition
* [ ] Adaptive retrieval
* [ ] Evidence coverage/conflict detection
* [ ] End-to-end migration evaluation

---

# Development Notes

Implementation decisions and entity-aggregation progress are documented in:

```text
docs/entity-aggregation-log.md
```

Earlier RAG design notes are retained in:

```text
docs/notes.md
```

---

## Design Principle

The central design principle of this project is:

> **When evidence is uncertain, preserve uncertainty instead of manufacturing certainty.**

For software migration, incomplete evidence can trigger additional retrieval.

Incorrectly merged evidence can produce a confidently wrong migration recommendation.

The architecture is therefore designed to make evidence relationships explicit, inspectable, and independently evaluable before those relationships are passed to a language model.
