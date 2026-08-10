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

The current implementation covers Level 1 extraction, entity resolution / evidence aggregation, and a Retrieval v1 baseline (dense + sparse + hybrid + version filtering), benchmarked end to end against a real pydantic 1.10.x → 2.x migration corpus. See [Benchmark Results](#benchmark-results-stage-7-baseline-stage-8a-gold-set-remediation) below.

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

The project currently includes **150 passing tests** across entity models, candidate blocking, hard cannot-link constraints, pairwise scoring, precision-first linking, Level 1 extraction (including deliberately adversarial "don't over-extract" cases), source-aware chunking, dense/sparse/hybrid retrieval, version-interval filtering (including version precision), and the evaluation harness. 10 of these were added across Stage 8A/8A.1 specifically to lock in the fixes made during gold-set remediation (`ChangeType.BEHAVIOR_CHANGED` isn't special-cased anywhere in aggregation, version precision is derived not manufactured, `migration_action_text` extraction and threading through the linker).

Several tests intentionally focus on difficult negative cases: evidence that shares a symbol or similar language but should **not** be merged (Level 2), and statements that merely mention a symbol without describing a change (Level 1).

There are also five pre-existing failures in legacy `retriever.py`/`vector_store.py` tests caused by historical interface mismatches, predating this work. They're intentionally being left alone: those two modules are expected to be replaced by a Hybrid Retrieval / Qdrant layer, so realigning tests to an interface likely to be rewritten has low value. They'll be revisited in their own commit once that layer's fate is decided.

---

# Benchmark Results (Stage 7 baseline, Stage 8A/8A.1/8A.2 gold-set remediation)

A deterministic baseline was frozen (chunking → dense/sparse/hybrid → Recall@K/MRR/nDCG) and benchmarked *before* considering an LLM extraction fallback, reranker, or Late Chunking -- adding any of those first would make it impossible to tell whether a later improvement came from retrieval or from more/better-extracted evidence.

**Gold Set v1: FROZEN.** Three rounds of human review against the official pydantic migration guide (Stage 8A/8A.1/8A.2) found real factual/completeness/taxonomy/wording/scope issues; all are corrected, and the numbers below are the frozen baseline. **The gold set was corrected for accuracy, not for score.** Gold set identity is tracked as machine-readable metadata inside the gold file itself:

```json
{"name": "Pydantic Gold Set v1", "gold_set_version": "1", "migration_scope": "1.10.x -> 2.x", "review_revision": 3, "status": "human-reviewed / frozen", "source_commit": "33163fd"}
```

Tagged `pydantic-gold-v1`. Going forward, Stage 8B does not modify this gold set to make retrieval scores look better -- reopening it requires a real factual/completeness/taxonomy error, and becomes a new revision (v1.1/v2), never a silent edit to v1. See `docs/entity-aggregation-log.md` "Gold Set v1 FROZEN".

**Corpus**: pydantic 1.10.x → 2.x only (no internal 2.x churn), grounded in the real [official migration guide](https://docs.pydantic.dev/latest/migration/) -- original short-form notes, not copied verbatim, covering BaseModel method renames, config renames, field/validator changes, generics/dataclass changes, moved/dependency-split symbols, and behavior changes, plus a "Stable in v2" section of facts that *didn't* change (for negative-query grounding). Run through the actual Level 1 → Level 2 pipeline (no hand-invented ids): 3 source documents → 76 chunks → 34 extracted `UnresolvedChange` claims → 27 resolved `ChangeRecord`s (7 deduplicated across independent migration-guide/release-note evidence via real pairwise resolution, 0 cannot-link vetoes needed). Every `DEPRECATED`/`MOVED`/`REMOVED` fact was audited for a real recommended action (`replacement_symbol` or, when it isn't a clean symbol swap, a free-text `migration_action_text` -- e.g. "use dicts instead"): 14 of 15 carry one; the 1 that doesn't (`stricturl`) is intentional -- no 1:1 replacement is verifiable from the official source, and the gold query was worded accordingly rather than implying one exists. `replacement_symbol` names what to call, not necessarily the complete diff (e.g. `from_orm`'s full action also needs a `model_config` change stated in its evidence text) -- see the semantics note in `data/gold/deprecated_action_audit.md`.

**Gold set**: 48 queries (`data/gold/pydantic_gold_queries.json`) across 10 taxonomy buckets (exact_symbol, natural_language paraphrase, single_change, multi_change, config_change, dependency_change, behavioral_change, negative, underspecified_symbol, legacy_symbol), each carrying real `required_change_ids`, `relevant_evidence_ids`, and (for negatives) `stability_evidence_ids` resolved from the pipeline output above, not placeholders. `config_change` (3) and `behavioral_change` (3) are short of the target 5 -- see Known Limitations below, not padded to hit a number. Three `evaluation_scope` values, only one of which feeds the core aggregate:

- **`change_retrieval`** (42 queries) -- the core Dense/BM25/Hybrid Recall@K table below.
- **`stability`** (5 queries, the negatives) -- `required_change_ids` is always vacuously empty, so change-level Recall@K is trivially 1.0 regardless of retrieval quality; not a meaningful signal for the core aggregate, reported separately.
- **`query_planner`** (1 query, `q_amb_01`) -- its 3-symbol required set is an editorial judgment call about what an underspecified query "should" mean, not a single retrieval ground truth; scoring it in the core table would penalize retrieval for a question that doesn't have one correct answer.

## Aggregate (change-level, `required_change_ids`, 42 `change_retrieval`-scope queries)

| Retrieval | Recall@5 | Recall@10 | MRR | nDCG@5 |
|---|---|---|---|---|
| Dense | **0.964** | 0.964 | **0.889** | **0.899** |
| BM25 (sparse) | 0.810 | 0.810 | 0.766 | 0.771 |
| Hybrid (RRF) | 0.952 | 0.952 | 0.875 | 0.895 |
| Hybrid + version filter | 0.929 | 0.929 | 0.863 | 0.880 |

Dense leads on every metric here (post remediation); Hybrid stays close behind on all of them. See "Hybrid does not strictly dominate Dense" below -- an examined, reproducible finding, not noise. Per the explicit review principle applied throughout: these numbers are reported as produced, not tuned toward a preferred ranking of Dense vs. Hybrid.

## Per query type (Recall@5, `change_retrieval` scope only)

| Query type | Dense | BM25 | Hybrid |
|---|---|---|---|
| exact_symbol | 1.000 | 1.000 | 1.000 |
| natural_language | 0.833 | **0.167** | 0.667 |
| single_change | 1.000 | 0.875 | 1.000 |
| multi_change | 0.917 | 0.833 | 1.000 |
| config_change | 1.000 | 0.667 | 1.000 |
| dependency_change | 1.000 | 1.000 | 1.000 |
| behavioral_change | 1.000 | 1.000 | 1.000 |
| legacy_symbol | 1.000 | 1.000 | 1.000 |

`natural_language` is still the clearest case for why hybrid exists at all: BM25 collapses to 0.167 on paraphrased questions with no exact symbol name, while dense holds up at 0.833. But hybrid (0.667) doesn't fully preserve dense's score here -- see below. `stability` (negatives) and `query_planner` (`q_amb_01`) are excluded from this table, reported separately (see below and the module docstring in `scripts/run_pydantic_benchmark.py`). Full per-type table for all four modes: `data/benchmark/per_query_type_results.csv`. Full per-query detail: `data/benchmark/per_query_results.csv`.

## Hybrid does not strictly dominate Dense

Reciprocal Rank Fusion sums *rank-based* scores across retrievers; it does not just take the best rank a document achieved in either list. A chunk BM25 never retrieves at all contributes zero credit from that side, so a chunk dense ranks very highly (even #1) can still be out-accumulated by chunks that both retrievers rank only moderately well. Confirmed directly on this corpus: `q_nl_03` ("How do I validate a plain dict into a model object now?") -- dense finds `BaseModel.parse_obj` at rank 4 (a clean top-5 hit on its own), BM25 never finds it at all, and the *real* RRF fusion pool the benchmark actually uses (top_k=10 → a 40-candidate fused pool, reconstructed exactly, not approximated) ranks it 13th -- outside top-10. Recall@5 for this single query: Dense 1.0, Hybrid 0.0.

This is a real property of RRF, not a bug, and it's the reason Hybrid's aggregate Recall@5 sits below Dense's in this run. It's also a concrete, examined argument for why a reranker (Stage 8B candidate) sits over the *union* of dense+sparse candidates rather than assuming a fused ranking is always at least as good as its best input.

## Failure analysis (re-run post Stage 8A.2 remediation)

Reading `data/benchmark/per_query_results.csv` (the authoritative source, `change_retrieval` scope only) directly: 2 queries have Hybrid Recall@5 < 1.0 -- `q_nl_02`, `q_nl_03` (1 of the 42 -- `q_nl_02` -- fails under every mode; `q_nl_03` only under Hybrid). Both were re-diagnosed with dense/sparse ranks (pool-size-independent, safe at any depth) and hybrid's rank reconstructed at the *exact* fusion pool size the benchmark itself uses (top_k=10 → 40 candidates fused, not a bigger diagnostic-only pool -- an earlier draft of this diagnostic used a 200-candidate pool for "how deep would we need to look" and got a materially different, misleading hybrid ranking for some queries because RRF's fusion pool size changes the fused order; that inconsistency was caught and fixed before these numbers were written down).

| Query | Required | Dense rank | Sparse rank | Hybrid rank (real pool) | Classification |
|---|---|---|---|---|---|
| `q_nl_02` | `BaseModel.construct` | 20 (top 20, not top 10) | not found (top 50) | 34 (of 40) | **RANKING** |
| `q_nl_03` | `BaseModel.parse_obj` | 4 (top 5) | not found (top 50) | 13 (of 40) | **RANKING** |

- **RANKING** (both): the fact is correctly extracted, indexed, and findable by at least one retriever within a reasonable window -- `q_nl_03` even lands a clean dense top-5 on its own. Not SEMANTIC_MISMATCH (that would mean absent even from a wide net). → reranker candidate, not addressed in Stage 8A per scope.
- No **CORPUS_GAP**, **EXTRACTION_GAP**, **LABEL_ERROR**, or **VERSION_FILTER_ERROR** found: both facts are demonstrably present and extracted (dense finds both in the top 20), the gold labels were re-verified three times during remediation, and `hybrid_version_filtered`'s numbers track `hybrid` closely throughout (no distortion traceable to the filter).

**`q_amb_01` (`evaluation_scope: "query_planner"`, excluded from the core table above)**: all four retrieval modes score 0.000 -- Dense's best of its 3 required changes only reaches rank 23-25 of 76 chunks. Classified **UNDERSPECIFIED_SYMBOL**, not RANKING: the query is a single four-letter bare term ("`parse`") genuinely matching multiple real symbols (`parse_obj`/`parse_raw`/`parse_file`, plus a non-required look-alike `parse_obj_as`), diluting relevance across all of them rather than pointing at one. → symbol/context-expansion candidate (a future query-understanding benchmark), not a retrieval-quality problem and not addressed in Stage 8A per scope.

**`stability` scope (5 negatives, excluded from the core table above)**: all score Recall@5 = 1.000 under every mode, by construction (empty required set) -- not reported as a retrieval-quality result, just confirmation the vacuous-recall behavior is working as designed.

Two more findings came directly from running the Stage 7 benchmark against real data, both already fixed (with regression tests) before those numbers were produced:

- **Chunking granularity bug** -- `migration_guide`/`official_docs` chunking bundled every bullet under a heading into one chunk (e.g. all 11 `BaseModel` method renames as one chunk's embedding), diluting the signal for any single fact. Change-level Recall@5 before/after switching to per-bullet chunking whenever a section is itemized: dense 0.604→0.927, sparse 0.542→0.844, hybrid 0.635→0.958 (Stage 7 numbers, pre-Stage-8A-correction). This was the single largest lever pulled in Stage 7 -- bigger than the retrieval algorithm choice itself.
- **Version-interval comparison bug** -- `(2,) < (2, 0, 0)` under plain tuple comparison, so a bare "v2" query and a "2.0.0"-tagged chunk were wrongly treated as non-overlapping, collapsing `hybrid_version_filtered` to Recall@5 = 0.208 in an early Stage 7 run. Fixed by padding tuples to equal length before comparing (`src/retrieval/version_filter.py`).

**Known limitation, not fixed**: `config_change` and `behavioral_change` gold buckets are thinner than intended (3 queries each, not 5) because several real config-setting renames (`orm_mode`, `schema_extra`, bare `Optional`, etc.) never became `UnresolvedChange` claims at all -- `symbol_normalization.py` deliberately excludes bare, non-dotted backtick words from symbol detection (to avoid misreading parameter names like `` `timeout` `` as symbols), which also excludes bare config-key names. Real Level 1 extraction-coverage gap, not a retrieval failure, and not silently patched (loosening the detector would reopen exactly the false-positive failure mode a regression test guards against).

**Version filter ablation caveat**: this corpus is scoped to a single target version (2.0.0), so `hybrid_version_filtered` has little room to differ from `hybrid` here -- the filter can only meaningfully help/hurt on a corpus spanning multiple versions with genuinely conflicting content, which this single-transition corpus doesn't exercise. Not evidence the filter doesn't work; evidence this corpus can't test it.

**`multi_change` is not version-path multi-hop**: this benchmark covers exactly one version transition (1.10.x → 2.x). `multi_change` queries combine several changes that co-occur *within* that one transition (e.g. a class using both `.dict()` and `.parse_obj()`) -- not a chain of sequential transitions (v2→v3→v4→v5). True multi-hop evaluation needs a corpus spanning multiple transitions and remains future work; nothing in this README or the benchmark code claims to test it.

Reproduce: `python -m scripts.build_pydantic_benchmark_corpus` → `python -m scripts.generate_pydantic_gold_set` → `python -m scripts.run_pydantic_benchmark` → `python -m scripts.diagnose_failed_queries` (each rebuilds `data/entities.db` and both indices from scratch; gold set ids are content-derived and regenerate automatically from the corpus, never hand-preserved). Regenerate the human-review checklist with `python -m scripts.generate_gold_review_checklist`; the deprecated-action completeness audit with the numbers above is `data/gold/deprecated_action_audit.md`.

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
* [ ] true version-path multi-hop migration queries (v2→v3→v4→v5 chains; `multi_change` benchmarks multiple co-occurring changes within one transition today, which is different -- see Benchmark Results)
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

* [x] Recall@K, MRR, nDCG -- implemented and run for real (see [Benchmark Results](#benchmark-results-stage-7-baseline-stage-8a-gold-set-remediation))
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
* [x] Real benchmark corpus + 48-query gold set (pydantic 1.10.x → 2.x)
* [x] Dense vs. sparse vs. hybrid vs. hybrid+version-filter benchmark, per-query-type slicing, failure analysis
* [x] Stage 8A/8A.1/8A.2: gold-set factual/completeness/taxonomy/scope/wording remediation across three human review rounds (4 factual fixes, 3 deprecated-only→actionable fixes, taxonomy renamed and split, `BEHAVIOR_CHANGED` applied + downstream-impact audited, minimal version-precision representation, stability evidence for negative queries, `evaluation_scope` 3-way split) -- see `docs/entity-aggregation-log.md`
* [x] **Gold Set v1 frozen** (tag `pydantic-gold-v1`, `status: "human-reviewed / frozen"`, `source_commit: 33163fd`) -- reopening requires a real factual/completeness/taxonomy error, never a score-motivated edit; becomes v1.1/v2 if it happens

### In Progress / Next

* [ ] Reranker (candidate: fixes RANKING-classified failures where the right chunk is indexed but scores too low, e.g. `q_nl_02`/`q_nl_03`, and the concrete finding that RRF hybrid doesn't strictly dominate dense)
* [ ] Query/symbol context expansion (candidate: fixes UNDERSPECIFIED_SYMBOL failures like `q_amb_01`)
* [ ] LLM-based extraction fallback (interface already exists in `llm_fallback.py`; not wired to a live model -- benchmark above is what will justify whether/where it's worth it)
* [ ] Migration Chain Recall metric
* [ ] Config-setting-rename extraction coverage (bare non-dotted symbol names currently excluded by design -- see Benchmark Results known limitations)
* [ ] Full SemVer interval representation (Stage 8A added only MAJOR/MINOR/PATCH precision tagging, deliberately not prerelease ordering, wildcard ranges, or `[2.0.0, 3.0.0)`-style intervals)

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
