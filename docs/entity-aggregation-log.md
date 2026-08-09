# Entity / Symbol Layer + Evidence Aggregation — Implementation Log

This file tracks the migration-assistant entity/symbol layer and Level 2
evidence-aggregation work. `docs/notes.md` is the separate day-by-day
learning journal and is not touched by this effort — this log is appended
to, never overwritten, after each stage.

Scope for this pass: entity/symbol data layer + Level 2 aggregation
(candidate generation → pairwise resolution → cannot-link constraints →
evidence link) only. Level 1 extraction (turning raw release note / PR
diff / migration guide text into `UnresolvedChange`/`Evidence` candidates)
is explicitly out of scope — `UnresolvedChange` in `src/entities/models.py`
is the interface contract a future extraction step must satisfy.

## Stage 1 — Cleanup: remove unused Shakespeare-specific code

**What**: Deleted `src/shakespeare_loader.py`, `src/tools/shakespeare_search.py`,
`src/benchmark_loader.py`, `src/evaluation/` (unfinished stub),
`scripts/build_vector_store.py`, `scripts/demo_retrieval.py`,
`tests/test_shakespeare_loader.py`, `tests/test_benchmark_loader.py`,
`data/corpus/`, `data/benchmark/`, and the built `chroma_db/` index.
Added `chroma_db/` and `data/entities.db` to `.gitignore`.

**Why**: The project is transitioning from the Shakespeare RAG demo to the
Software Version Migration Assistant; this code won't be used going
forward. Kept the generic, domain-agnostic RAG infra (`document_loader.py`,
`chunker.py`, `embedding.py`, `vector_store.py`, `retriever.py`,
`prompt_builder.py`) since it's reusable for ingesting release notes / PR
diffs / migration guides later. `docs/notes.md`, `docs/architecture-day1.png`,
and `README.md` were left untouched.

**Safety note**: this repo already had git history with a GitHub remote
(`KianaShi/rag-chatbot`); a local-only safety commit was made before
deleting anything, and nothing was pushed.

**Files changed**: see git log — commit "Remove Shakespeare-specific code,
corpus, benchmark, and built vector store".

## Stage 2 — Entity/symbol data layer

**What**: Added `src/entities/models.py` (dataclasses: `Symbol`,
`ChangeAttributes` / `UnresolvedChange` / `ChangeRecord`, `Evidence`,
`CannotLinkConstraint`, `EvidenceLink`, plus enums for source type, change
type, link type/method, confidence tier, review status, cannot-link reason,
and pairwise decision) and `src/entities/store.py` (SQLite-backed
repository: schema DDL, CRUD, and the symbol-blocking query).

**Why**: `change_id` needed to be a real, queryable cross-document foreign
key rather than something inferred after the fact from semantic similarity.
A relational store (SQLite, stdlib, no new dependency) fits the
graph-shaped change/evidence/link/constraint data much better than
ChromaDB's flat vector+metadata model; ChromaDB remains the semantic layer
for chunk embeddings elsewhere in the pipeline. `ChangeAttributes` is a
shared base between `UnresolvedChange` (the not-yet-linked, not-yet-real
change_id shape that a future Level 1 extractor must produce) and
`ChangeRecord` (the persisted, canonical entity), so aggregation code can
compare either structurally without caring which one it received.

**Files added**: `src/entities/__init__.py`, `src/entities/models.py`,
`src/entities/store.py`, `tests/test_entities_store.py`.

## Stage 3 — Level 2 aggregation pipeline

**What**: Added `src/aggregation/`:
- `config.py` — all pairwise scoring weights, decision thresholds
  (`INFERRED_HIGH_CONFIDENCE_THRESHOLD`, `AMBIGUOUS_LOWER_BOUND`), and the
  change-type compatible-pair allowlist, as named constants for later gold-set
  calibration.
- `blocking.py` — candidate generation, purely structural (symbol name +
  package, optional version_to pre-filter). No embedding similarity here.
- `constraints.py` — the four hard cannot-link rules (incompatible version
  transition, non-overlapping change semantics, separate release events,
  explicit different references), each a deterministic structural
  comparison. Each check returns a `ConstraintResult(allowed, reason,
  detail)` rather than a bare bool, so a false split is always traceable to
  the specific rule and values that fired it.
- `pairwise.py` — resolves one (unresolved change, candidate) pair: hard
  constraints first (veto), then a shared explicit reference (outright
  match), then a weighted score (symbol exact match, version compatibility,
  change-type match, embedding-based summary similarity) classified into
  MATCH_INFERRED / AMBIGUOUS / NO_MATCH via the config thresholds. Returns
  `PairwiseResult` carrying a `PairwiseScore(total, signals={...})` with the
  per-signal breakdown, not just the final number, for regression diffing
  later.
- `linker.py` — orchestrates candidate generation → pairwise resolution →
  cannot-link → evidence link per evidence item, sequentially against the
  existing change_id registry (not batch clustering, to avoid transitive
  merges). Exactly one confident match resolves normally; zero matches
  originates a new change_id; more than one plausible match (conflicting
  explicit refs, or any AMBIGUOUS candidate alongside others) is never
  auto-picked — every plausible candidate gets an AMBIGUOUS/NEEDS_REVIEW
  link instead. Cannot-link constraints against ruled-out candidates are
  persisted once the evidence's identity is settled, anchored to the
  resolved change_id, for later false-split debugging.

**Why**: Matches the precision-first requirement (false split > false
merge) and avoids the transitive-merge risk of plain hierarchical
clustering over evidence. Symbol is used only as a blocking key throughout
— identity is always decided by explicit reference or scored pairwise
resolution, never by blocking-key equality or embedding similarity alone.

**Files added**: `src/aggregation/__init__.py`, `config.py`, `blocking.py`,
`constraints.py`, `pairwise.py`, `linker.py`, and
`tests/test_blocking.py`, `tests/test_cannot_link.py`,
`tests/test_pairwise_resolution.py`, `tests/test_evidence_linker.py`.

## Stage 4 — Presentation layer + test run

**What**: Added `src/presentation/confidence_view.py` — `describe_link()`
maps `confidence_tier` + `review_status` to a fixed, human-readable label
(e.g. "Likely the same change (needs human review before use)"); no
caller-facing path reads `link_confidence` or the raw tier/status enum
directly. Added `tests/test_confidence_view.py`.

Ran the full suite: 35 new tests across the 6 new modules all pass. 5
pre-existing failures remain in `tests/test_retriever.py` /
`tests/test_vector_store.py` — unrelated to this work (those two source
files were never touched; the tests call function signatures that don't
match the current `retriever.py`/`vector_store.py` implementations, a
pre-existing mismatch from before this session).

**Files added**: `src/presentation/__init__.py`,
`src/presentation/confidence_view.py`, `tests/test_confidence_view.py`.

## Stage 5 — Level 1 extraction (deterministic-first)

Repo renamed on GitHub to `AI-Software_Version_Migration_Assistant`; local
`origin` remote updated to match. README confirmed the architecture
described there matches what's built so far.

**Scope boundary, restated because it matters**: Level 1 answers "what
does this piece of evidence claim?" only. It never decides which
`ChangeRecord` a claim belongs to and never generates a `change_id` --
that's exclusively `src/aggregation/linker.py`'s job (Stage 3, untouched).
`extract_changes()` returns `UnresolvedChange` objects and nothing else.
`tests/test_change_extraction.py::test_never_generates_a_change_id`
asserts this structurally (`UnresolvedChange` has no `change_id` field at
all, so there's nothing to accidentally set).

Decided against fixing the 5 pre-existing `test_retriever.py` /
`test_vector_store.py` failures now: those two modules are expected to be
replaced by a Hybrid Retrieval / Qdrant layer later, so realigning tests
to an interface that's likely to be rewritten soon has low expected
value. Left as-is with the same "pre-existing, unrelated" note; revisit
in its own commit once the retrieval layer's fate is decided.

**What**: Added `src/extraction/`:
- `models.py` — `SourceDocument` (document_id, source_type, raw_text,
  provenance, url, version, date, document_refs) and `ExtractionConfidence`
  (EXPLICIT / INFERRED) — deliberately separate from `src.entities.models`
  to keep the "claims vs. identity" boundary visible in the import graph,
  not just in a comment.
- `sources.py` — `parse_release_note` / `parse_migration_guide` /
  `parse_official_docs` / `parse_github_pr_issue`. Each normalizes raw
  text you already have, plus its metadata, into a `SourceDocument`; none
  of them fetch anything over the network (no GitHub API / docs-site
  crawling in this pass -- that's separate infrastructure requiring auth
  and rate-limit handling).
- `version_normalization.py` — `find_version_mentions()` /
  `parse_version_expression()` parse "v1.2", "1.2.x", "since 1.2",
  "removed in 2.0", "1.2 to 2.0", "1.2 - 2.0", and "between 1.2 and 2.0"
  into a structured `VersionMention(normalized, qualifier, span,
  normalized_end)`. Only syntax is normalized (strip "v" prefix, strip
  ".x" wildcard suffix) -- no semver ordering/comparison, since nothing
  downstream needs it yet (constraints.py compares version strings for
  equality).
- `symbol_normalization.py` — `normalize_symbol()` / `find_symbol_mentions()`
  fold `FooClient.create()`, `foo.FooClient.create`, `FooClient#create`,
  `FooClient::create` into the same canonical `Symbol(name="FooClient.create",
  package=..., kind=...)`. Backtick code spans are the primary signal;
  un-backticked mentions are only recognized when they look unambiguously
  like a call (`Class.method()`), and a backtick-quoted bare word (e.g.
  `` `timeout` ``, a parameter name) is deliberately excluded from symbol
  detection -- an early version of this regex misread every quoted
  parameter name as its own symbol before the "requires a dotted path or
  trailing `()`" rule was tightened.
- `llm_fallback.py` — `LLMExtractor` protocol + `NotConfiguredLLMExtractor`,
  which declines everything. No LLM is wired into this repo (README:
  "OpenAI API (planned)"); this is the seam a future implementation plugs
  into, not a real integration.
- `change_extraction.py` — `extract_changes(document, default_package,
  llm_extractor=None)`, deterministic-first: regex/keyword rules for a
  fixed vocabulary of change verbs (removed/renamed/deprecated/moved/
  signature-changed/behavior-changed) plus dedicated replacement-style
  patterns ("X was replaced by Y", "X is deprecated in favor of Y", "use Y
  instead of X") that correctly produce *one* claim about two symbols
  instead of two claims. A statement naming more than one symbol that
  isn't a replacement pattern is split once on conjunctions ("and"/";")
  and each half re-extracted independently, so "`A` was removed and `B`
  was renamed" yields two separate `UnresolvedChange` records rather than
  one merged/garbled one. Markdown headings carrying a version (e.g. `##
  v5.0.0`) become ambient context for statements under them that have no
  inline version of their own -- used, but always as `INFERRED` confidence
  with `extraction_method` containing `ambient_version`, never `EXPLICIT`.
  A statement with a change-verb but no attributable symbol, or a symbol
  mention with no change-verb nearby, extracts nothing rather than
  guessing. The LLM fallback is only invoked when a statement has a symbol
  mention, no deterministic change-verb match, and an ambiguous signal
  word (breaking/note/warning/updated/modified/change(d/s)) -- and with no
  extractor configured, that path still safely returns nothing.

**Why**: Matches the precision-first principle established in Level 2,
applied one stage earlier: Level 1 is exactly as willing to emit *nothing*
as Level 2 is to leave two changes unmerged. Deterministic-first (regex on
explicit version/PR/symbol/keyword signals) keeps extraction cheap and
debuggable; the LLM fallback is reserved for genuinely ambiguous natural-
language semantics, per your instruction, and isn't wired to a live model
in this pass since none exists in the repo yet.

**Files added**: `src/extraction/__init__.py`, `models.py`, `sources.py`,
`version_normalization.py`, `symbol_normalization.py`, `change_extraction.py`,
`llm_fallback.py`, and `tests/test_source_adapters.py`,
`tests/test_version_normalization.py`, `tests/test_symbol_normalization.py`,
`tests/test_change_extraction.py` (43 new tests, all passing).

**Files modified**: `src/entities/models.py` (additive, backward-compatible:
`ChangeType.REPLACEMENT`; `ChangeAttributes.replacement_symbol` and
`.parameters`; `SourceType.PR_DIFF` renamed to `GITHUB_PR_ISSUE` (never
referenced elsewhere, zero-cost rename) plus new `OFFICIAL_DOCS`;
`UnresolvedChange.extraction_confidence` and `.extraction_method`) and
`src/entities/store.py` (schema/row-mapping updated for the two new
`ChangeAttributes` columns). Verified via the existing Stage 2/3 test
suite (35 tests) that this didn't break anything before proceeding.

Full suite after this stage: 86 passed, the same 5 pre-existing
`test_retriever.py`/`test_vector_store.py` failures (deliberately not
touched, see above).

## Stage 6 — Retrieval v1 baseline (dense + sparse + hybrid, evaluation harness)

Explicit decision, stated before this stage started: baseline retrieval
first, evaluate it, and only then decide whether wiring a real LLM
fallback into Level 1 is worth it -- LLM fallback is a recall booster on
top of an already-tested deterministic main path, not a blocker. Also
explicitly deferred: Late Chunking, rerankers, and Agentic RAG all wait
for this baseline to exist so they can be evaluated as ablations against
it rather than added on faith.

**What**: Added `src/retrieval/`:
- `models.py` -- `Chunk` (chunk_id, text, source_document_id, source_type,
  provenance, package, version, symbols, `evidence_id`) and
  `RetrievedChunk` (chunk, score, rank). `evidence_id` is the traceability
  hook requested up front: nullable, not populated by anything in this
  stage, but present so a retrieved chunk can eventually be mapped back to
  the `Evidence`/`ChangeRecord` that Level 1/2 produced from it, once/if
  extraction ever runs per-chunk instead of per-document. Chunk is
  deliberately a distinct type from `entities.models.Evidence`, not a
  reuse of it -- a chunk is an index-time retrieval unit that may or may
  not ever have had Level 1 run on it; conflating the two would couple
  retrieval to extraction having already happened.
- `chunking.py` -- source-aware, not Late Chunking: release notes chunk
  per bullet entry within each version-heading section (changelogs are
  itemized -- one bullet is usually one change); migration guides and
  official docs chunk per heading-scoped section (prose-heavy, coarser
  granularity is more coherent); PR/issue bodies chunk per paragraph (no
  heading/itemization to lean on, and "relevant discussion" beyond the
  body text isn't available without a real GitHub API integration, which
  is still out of scope -- see Stage 5's sources.py note). Known
  limitation, not fixed this pass: a version stated in a top-level heading
  doesn't cascade down to child headings below it, only to text directly
  under that heading.
- `version_filter.py` -- `VersionInterval` + `intervals_overlap()`, reusing
  `extraction.version_normalization` rather than re-parsing version
  syntax. `parse_version_key()` turns a normalized version string into a
  tuple of ints so `1.2 < 1.10` compares correctly (not lexically). Query
  and chunk versions both become intervals (a bare version is a
  degenerate single-point interval); overlap is a bounds check, not
  string equality, so a query for "1.2 to 2.0" matches a chunk tagged
  "1.5" even though the strings never match.
- `dense_index.py` -- thin wrapper over the existing `embedding.py` +
  `vector_store.py` (ChromaDB), specialized to `Chunk`. Required a small
  backward-compatible extension to `vector_store.add_chunks()`: an
  optional `ids` parameter (default `None` preserves the old
  document-name-derived-id behavior) so chunks can be indexed under their
  own `chunk_id` instead of an auto-generated one -- otherwise retrieval
  results couldn't map cleanly back to `Chunk` objects.
- `sparse_index.py` -- hand-rolled Okapi BM25, no new dependency (matches
  this repo's existing "build the pipeline from scratch" approach). The
  tokenizer keeps a dotted identifier like `FooClient.create` as one token
  *and* splits it into `fooclient`/`create`, so a bare method-name query
  still matches -- this is the concrete reason to have a sparse baseline
  at all, since exact API/class/parameter names are exactly what dense
  embeddings tend to blur.
- `filters.py` -- post-retrieval filtering (package equality, version
  overlap) applied identically after dense, sparse, or hybrid retrieval,
  so the three are compared under the same filter semantics. Applied
  after ranking rather than pushed into the index query, since neither
  Chroma's `where` nor the hand-rolled BM25 index supports interval-
  overlap filtering natively. A chunk with an unknown package/version is
  kept, not dropped -- missing metadata isn't evidence of a mismatch.
- `hybrid.py` -- Reciprocal Rank Fusion over dense + sparse rankings by
  rank position only (dense distances and BM25 scores aren't on
  comparable scales), one constant (`RRF_K = 60`, the standard default),
  no per-source weight tuning.
- `retrieval.py` -- `retrieve_dense` / `retrieve_sparse` / `retrieve_hybrid`
  sharing one signature and the same `filters.apply_filters` step, so
  `evaluation.py` can swap between them against the same gold set.
  Over-fetches (4x top_k) before filtering, since filtering after ranking
  can otherwise leave fewer than top_k results even when enough exist
  further down the raw ranking.
- `evaluation.py` -- `recall_at_k` / `mrr` / `ndcg_at_k`, all item-id-
  agnostic (they never assume the ids are chunk ids). `GoldQuery` is
  annotated at the change_id level per the design brief
  (`required_change_ids`, not a single expected chunk); `resolve_to_change_ids()`
  is the injected chunk-id-ranking -> deduplicated-change-id-ranking step
  that lets Recall@K run today without the full Level 1/2 pipeline wired
  end-to-end per chunk. Upgrading to Migration Chain Recall later is a new
  metric function operating on the same resolved id lists, not a
  re-annotation of the gold set.

**Files added**: `src/retrieval/__init__.py`, `models.py`, `chunking.py`,
`version_filter.py`, `dense_index.py`, `sparse_index.py`, `filters.py`,
`hybrid.py`, `retrieval.py`, `evaluation.py`, and `tests/test_chunking.py`,
`tests/test_version_filter.py`, `tests/test_dense_index.py`,
`tests/test_sparse_index.py`, `tests/test_filters.py`, `tests/test_hybrid.py`,
`tests/test_retrieval_evaluation.py`, `tests/test_retrieval_integration.py`
(49 new tests, all passing -- the last file builds a small corpus and
runs dense/sparse/hybrid side by side, confirming BM25 wins an exact-
symbol-name query outright and that the version filter behaves
identically across all three retrieval modes).

**Files modified**: `src/vector_store.py` (`add_chunks` gained an optional
`ids` parameter, backward compatible).

**Note on a parallel automation**: partway through this stage, `git
status` showed `src/retrieval/models.py` and `chunking.py` already
committed and pushed to `origin/main` (commits "1" and "Create
chunking.py") that neither this session nor any command in it created.
Confirmed with you this is an intentional auto pull/commit/push tool you
run against this repo, independent of this session -- noting it here
since it means "local commit, not pushed" is no longer a safe assumption
to state about work in this repo going forward.

Full suite after this stage: 135 passed, the same 5 pre-existing
`test_retriever.py`/`test_vector_store.py` failures (still deliberately
untouched -- see Stage 5's note on why, now doubly true since a Hybrid
Retrieval baseline exists to eventually replace them with).

## Stage 7 — Retrieval Benchmark v1 (real corpus, real gold set, real numbers)

Explicit decision going into this stage (yours): benchmark the frozen
baseline before touching LLM fallback, reranker, or Late Chunking --
otherwise a later score change can't be attributed to retrieval quality
vs. more/better-extracted evidence. Scope locked to pydantic 1.10.x →
2.x only, not internal 2.x churn, specifically so the gold set would stay
clean and easy to hand-verify.

**Corpus**: researched the real official pydantic migration guide and
v2.0/v1.10.10 release info via WebFetch, then wrote original short-form
corpus text grounded in those real facts (not copied verbatim -- see
copyright policy) in `data/corpus/pydantic/{migration_guide,
release_notes,concepts}.md`. `scripts/build_pydantic_benchmark_corpus.py`
runs the actual Stage 5/6 pipeline over it end to end: chunking → Level 1
extraction → Level 2 aggregation → dense + sparse indices, with no
hand-invented ids anywhere -- every `change_id`/`evidence_id` referenced
by the gold set is something this script actually produced.

**Three real bugs found and fixed by running real data through the
pipeline** (each with a regression test, each confirmed via full-suite
rerun before moving on):

1. `src/aggregation/linker.py` silently dropped `replacement_symbol` and
   `parameters` when originating a new `ChangeRecord` -- the Stage 5
   schema extension added those fields to `ChangeAttributes` but the
   linker's change-origination path was never updated to pass them
   through. Every real REPLACEMENT/MOVED change's `replacement_symbol`
   was `None` in the DB until this was caught and fixed.
2. `src/extraction/change_extraction.py`'s `_REPLACEMENT_PATTERNS` had no
   "X was moved to Y" pattern, only "replaced by" / "deprecated in favor
   of" / "use X instead of" -- so two-symbol "moved to" statements (e.g.
   `pydantic.BaseSettings` → `pydantic_settings.BaseSettings`, a real,
   important Dependency-change fact) produced zero `UnresolvedChange`
   claims. Added a MOVED variant of the same pattern shape.
3. `src/retrieval/version_filter.py`'s `intervals_overlap()` compared
   version-key tuples of different lengths directly, so `(2,) < (2, 0,
   0)` under Python's default tuple ordering -- meaning a bare "v2" query
   and a "2.0.0"-tagged chunk were wrongly treated as non-overlapping.
   This alone collapsed the `hybrid_version_filtered` benchmark row to
   Recall@5 = 0.208 before it was caught. Fixed by padding both tuples to
   equal length (trailing zeros) before comparing.

**One chunking granularity bug, the single biggest lever in this stage**:
`migration_guide`/`official_docs` chunking (`_chunk_heading_aware`) put
an entire heading-section's text in one chunk, which was a reasonable
default for prose but wrong for `migration_guide.md`, which is itemized
exactly like a changelog -- every bullet under a heading (up to 11 of
them) got bundled into one chunk, diluting that chunk's embedding/BM25
signal across many unrelated facts. Unified `chunking.py`'s per-source
strategies into one `_chunk_by_section` that chunks per-bullet whenever a
section is a bulleted list and falls back to whole-section only for
actual prose -- granularity now follows content structure, not
source_type. Change-level Recall@5 before/after: dense 0.604 → 0.927,
sparse 0.542 → 0.844, hybrid 0.635 → 0.958.

**Gold set**: `scripts/generate_pydantic_gold_set.py` generates
`data/gold/pydantic_gold_queries.json` (48 queries, 9 taxonomy buckets)
by referencing real symbol names -- looked up against the live
`change_records` table at generation time -- rather than hand-typed hash
ids, so a typo can't silently desync the gold set from the corpus.
`config_change` and `behavioral_change` came in at 3 queries each instead
of the suggested 5: several real config-setting renames (`orm_mode`,
`schema_extra`, bare `Optional`, etc.) never produced an
`UnresolvedChange` at all, because `symbol_normalization.py` deliberately
excludes bare, non-dotted backtick words from symbol detection (Stage 5:
avoids misreading a quoted parameter name as a symbol). Left as an
honest, documented shortfall rather than padded or fixed by loosening
that detector, which would reopen the exact false-positive it exists to
prevent. This is a draft gold set -- the labels are real (grounded in the
real migration guide, generated against real pipeline output) but not
yet reviewed/signed off by you.

**Benchmark**: `scripts/run_pydantic_benchmark.py` runs all 48 queries
through `retrieve_dense` / `retrieve_sparse` / `retrieve_hybrid` /
`retrieve_hybrid` (+ version filter), scored both at the change level
(`required_change_ids`) and evidence level (`relevant_evidence_ids`),
aggregate and per-query-type, plus a 4-quadrant failure comparison
(dense-only / sparse-only / hybrid-fixes-both / all-fail). Final numbers
(change-level): Dense R@5=0.927, BM25 R@5=0.844, Hybrid R@5=0.958 (best),
Hybrid+version-filter R@5=0.938. `natural_language` query type is the
clearest result: BM25 R@5=0.167 vs. Dense/Hybrid 0.833 -- exactly the
"sparse wins on exact symbols, dense wins on paraphrase, hybrid keeps the
best of both" pattern the benchmark was designed to either confirm or
refute. Only 2 of 43 non-negative queries fail under every mode; both are
query-wording problems (an unusually distant paraphrase, and a bare
ambiguous term), not corpus or index gaps -- candidates for a reranker
and query decomposition respectively, not a bigger corpus. Full tables,
CSVs, and the version-filter ablation caveat (this single-target-version
corpus doesn't give the filter much room to show an effect) are in the
README's new "Benchmark Results (Stage 7)" section.

**Files added**: `data/corpus/pydantic/{migration_guide,release_notes,
concepts}.md`, `scripts/build_pydantic_benchmark_corpus.py`,
`scripts/generate_pydantic_gold_set.py`, `scripts/run_pydantic_benchmark.py`,
`data/gold/pydantic_gold_queries.json`, `data/benchmark/{aggregate_results,
per_query_type_results,per_query_results}.csv`,
`tests/test_evidence_linker.py::test_originated_change_carries_replacement_symbol_and_parameters`,
`tests/test_change_extraction.py::test_moved_to_statement_yields_one_change_with_replacement_symbol`,
`tests/test_version_filter.py::test_short_and_long_forms_*`,
`tests/test_chunking.py::test_migration_guide_chunks_per_bullet_when_itemized`.

**Files modified**: `src/aggregation/linker.py` (bugfix 1),
`src/extraction/change_extraction.py` (bugfix 2 -- new MOVED pattern),
`src/retrieval/version_filter.py` (bugfix 3 -- padded tuple comparison),
`src/retrieval/chunking.py` (chunking granularity fix, unified strategy),
`src/retrieval/evaluation.py` (added `query_type`/`from_version`/
`to_version`/`relevant_evidence_ids` to `GoldQuery`, `ndcg_at_5`,
`required_ids_attr` param on `evaluate_queries` so the same function
scores either id space), `README.md` (Benchmark Results section, status
checklist, retrieval architecture status).

Full suite after this stage: 140 passed, same 5 pre-existing
`test_retriever.py`/`test_vector_store.py` failures, untouched.

## Stage 8A — Benchmark Validation & Failure Diagnosis

Scope, as instructed: validate and diagnose only. No reranker or query-
rewrite code this stage. Pre-Stage-8A baseline: working tree was already
clean at commit `8e540dc` (Stage 7's commit) when this stage started, so
that commit *is* the snapshot -- gold set, benchmark scripts, and results
exactly as Stage 7 produced them. No redundant empty commit was made;
`8e540dc` is the reference point for all "before" comparisons in this
stage and in Stage 8B later.

### Step 1 — Gold set human review checklist (prepared, not yet reviewed)

`scripts/generate_gold_review_checklist.py` resolves every
`required_change_id`/`relevant_evidence_id` in the gold set back into
readable symbol/change_type/evidence-text against the live
`data/entities.db`, grouped by `query_type`, with `multi_hop` /
`ambiguous_alias` / `behavioral_change` / `negative` flagged for
priority review. Output: `data/gold/pydantic_gold_review_checklist.md`
(sent to you directly). This is a review aid, not an automated judgment
-- no query/label was auto-corrected or auto-flagged as wrong.

Three structural observations surfaced while assembling it (noted for
your review, not treated as conclusions):
- `q_config_03` and `q_behav_03` reference the identical change_id and
  evidence (`chg_6a2dc66d8dc05c78`, `Field` SIGNATURE_CHANGED) under two
  different taxonomy tags with different phrasing -- worth confirming
  that's intentional.
- `q_single_06` (`BaseModel.parse_file`) has `version_to="2"` instead of
  `"2.0.0"` -- the known bare-"v2" extraction artifact already documented
  in Stage 7, not a new bug, but visible on this record specifically.
- Of the four `ambiguous_alias` queries, only `q_amb_01` actually has
  multiple `required_change_ids` (3); `q_amb_02`/`03`/`04` each have
  exactly one, so they read closer to `exact_symbol`-with-an-old-name
  than genuinely ambiguous/multi-candidate queries.

**Status: waiting on your review before Step 5 (freeze).** Steps 2-4
below don't depend on gold-label corrections, so they proceeded without
waiting, per your instruction.

### Step 2 — Rank diagnosis for the two failing queries

`scripts/diagnose_failed_queries.py`: for each failing query, finds the
rank (out of a 50-candidate pull, corpus is 70 chunks total) at which
*any* chunk resolving to a required change_id first appears, per
retrieval mode.

**`q_nl_02`** -- "What's the new way to build a model instance while
skipping validation?" (gold: `BaseModel.construct` → `model_construct`,
`chg_cdb5bd04644c800d`)

| Mode | Rank | Top5 | Top10 | Top20 | Top50 |
|---|---|---|---|---|---|
| Dense | 17 | no | no | yes | yes |
| BM25 | not found | no | no | no | no |
| Hybrid | not found | no | no | no | no |

**`q_amb_01`** -- "What happened to `parse` in pydantic v2?" (gold: 3
changes -- `parse_obj`→`model_validate`, `parse_raw`→`model_validate_json`,
`parse_file` deprecated)

| Mode | Rank | Top5 | Top10 | Top20 | Top50 |
|---|---|---|---|---|---|
| Dense | 18 | no | no | yes | yes |
| BM25 | not found | no | no | no | no |
| Hybrid | 26 | no | no | no | yes |

Notable: for `q_nl_02`, Dense alone finds the target at rank 17, but
Hybrid (RRF over Dense+BM25) does *not* find it anywhere in the top 50 --
worse than Dense alone. This isn't a bug: RRF sums per-list rank scores,
so a chunk BM25 never retrieves at all gets zero credit from that side,
while other chunks that both retrievers rank moderately (even if neither
ranks them as high as Dense ranks this one) can out-accumulate it. Worth
knowing before assuming "hybrid can only help or tie" -- it can lose to
its best component on a per-query basis. `q_amb_01` doesn't show this
(Hybrid rank 26 sits between Dense's 18 and BM25's "not found").

### Step 3 — Failure classification

- **`q_nl_02` → RANKING.** Dense places the correct change within the
  top 20 of 70 total chunks (top ~24th percentile) -- the fact is
  correctly extracted, correctly indexed, and semantically close enough
  for embedding similarity to surface it, just not competitively enough
  for top 5. Not SEMANTIC_MISMATCH: that category requires absence from
  top 50 under every mode, which isn't true here (Dense finds it). →
  reranker candidate, per your mapping.
- **`q_amb_01` → AMBIGUOUS_SYMBOL.** The query is a single bare,
  four-letter term ("`parse`") that genuinely matches multiple real
  symbols in the corpus (`parse_obj`, `parse_raw`, `parse_file`, and a
  non-required look-alike `parse_obj_as`), diluting relevance across all
  of them rather than pointing at one. Rank data supports this reading
  over RANKING: even Dense alone, usually the strongest single signal in
  this benchmark, only gets the best of 3 required changes to rank 18 --
  worse than most single-hop/exact-symbol queries with an equally rare
  term but no ambiguity. → symbol/context expansion candidate, per your
  mapping, not a reranker problem (a reranker can't resolve which
  `parse_*` the user meant without more context to rerank against).

Neither failure is classified as CORPUS_GAP or EXTRACTION_GAP: in both
cases the required content is demonstrably indexed and extractable (both
appear within Dense's top 20), so the fact reaching the corpus and
surviving Level 1 extraction isn't in question -- only how it's ranked
against the specific query wording. Per your instruction, not defaulting
either one to "needs agentic decomposition."

### Step 4 — Version filter conclusion (recorded, not re-implemented)

Stage 7 result, restated for the record: Hybrid Recall@5 = 0.958 →
Hybrid+version-filter Recall@5 = 0.938 (a small decrease, not an
increase). Conclusion: this corpus is scoped to a single target version
(pydantic 2.0.0) with no genuinely conflicting multi-version content, so
the version-interval filter has essentially nothing to exclude that
wasn't already irrelevant for other reasons -- it cannot demonstrate a
real ablation effect (positive or negative) on this corpus. This is a
corpus-design limitation of Stage 7, not a verdict on whether version
filtering is a good idea; it stays unimplemented-changed and unthresholded
this stage, exactly as instructed. A real test of version filtering needs
a corpus spanning multiple versions with content that actually
contradicts across versions (e.g. a symbol that means different things in
1.x vs 2.x vs 3.x) -- noted here as a corpus requirement for whenever
that ablation is worth running for real, not committed to as a next step.

## Stage 8A (continued) — Gold Set Remediation

Baselines for this phase: `8e540dc` (Stage 7 benchmark), `60002e8`
(Stage 8A diagnosis/checklist v1). You reviewed the checklist against the
official pydantic migration guide yourself and found 4 factual/
completeness problems and 4 taxonomy/schema problems. This section is
the remediation of all of those, plus the systematic audit and downstream
impact review you asked to accompany them. Explicit scope boundary
observed throughout: no reranker, query rewrite, context expansion, new
embedding model, Late Chunking, LLM fallback, or full SemVer engine --
this stage is about making the gold set trustworthy, not improving
retrieval scores, and several scores did in fact go down as a direct
result, which is treated as correct behavior, not a regression to fix.

### 1. Factual corrections

**1A -- `q_dep_04`**: `migration_guide.md` said `pydantic.utils.to_camel`
moved to `pydantic.alias_generators.to_camel`. Real mapping (verified
against the official migration guide table): `utils.to_camel` →
`alias_generators.to_pascal`, and a *separate* function,
`utils.to_lower_camel` → `alias_generators.to_camel`. Corpus corrected to
state both real facts as two bullets. The query text didn't need to
change (it still asks about `utils.to_camel`); only the corpus fact did,
so the gold set's `required_change_ids`/`replacement_symbol` corrected
automatically on rebuild -- nothing hand-patched.

**1B -- `q_single_08`**: corpus said `BaseModel.json_schema()` was
replaced by `model_json_schema()`. `json_schema()` was never a real v1
method; the real v1 API is `BaseModel.schema()` (returns a dict).
Corrected the corpus fact and the query text ("I generate JSON schemas
with `BaseModel.schema()`. What should I use in v2?"), and updated the
gold generator's symbol reference from `BaseModel.json_schema` to
`BaseModel.schema`.

Both regenerated through the real pipeline (`build_pydantic_benchmark_corpus.py`
→ `generate_pydantic_gold_set.py`), not hand-patched -- change_id/evidence_id
are content hashes, so the corpus edit alone produces new, correct ids on
rebuild.

### 2. Migration-action completeness (status-only → actionable)

Principle applied: a `DEPRECATED`/`MOVED` fact that only says "X is
deprecated" without a `replacement_symbol` is incomplete for a *migration
assistant* even if factually true -- the corpus already had a clearer
recommended action available in two of three cases, and a better one
than "the deprecated import path" in the third.

- **2A `parse_obj_as`**: was `MOVED` → `pydantic.deprecated.tools.parse_obj_as`
  (a namespace whose own name says "deprecated" -- not a real recommended
  migration). Corrected to `DEPRECATED` → `TypeAdapter` (the real
  recommended replacement per the migration guide), with the legacy
  import path kept as a secondary sentence in the same corpus bullet
  (retrievable, but not the primary action).
- **2B `BaseModel.parse_file`**: was `DEPRECATED` with `replacement_symbol=None`
  ("no direct v2 replacement"). Corrected to `DEPRECATED` →
  `BaseModel.model_validate`, with the corpus stating the actual
  recommended action ("load the file yourself and pass the parsed data
  in"). This also incidentally fixed the version-precision artifact
  noted below (§ version precision) -- the old phrasing's bare "v2"
  mention is gone.
- **2C `BaseModel.from_orm`**: was `DEPRECATED` with `replacement_symbol=None`
  (the old phrasing -- "deprecated in favor of setting `from_attributes`
  on `model_config`" -- had a word between the connector and the target
  symbol, so the tight-phrasing replacement-pattern regex never captured
  a target). Corrected to `DEPRECATED` → `BaseModel.model_validate`, with
  the corpus stating the full action ("set `from_attributes` to `True`
  on `model_config` first").

**2D -- systematic audit of all `DEPRECATED`/`MOVED` records** (not just
the three you flagged): queried every record of those two change types
in the rebuilt DB (11 total) for `replacement_symbol IS NULL`. Result: **0
remaining** after the three fixes above (the other 8 -- `@validator`,
`@root_validator`, `parse_raw`, and 5 `MOVED` import-path facts -- already
had a real action from Stage 7). Full table with before/after and
reasoning: `data/gold/deprecated_action_audit.md`. No other change_type
(`REPLACEMENT`, `REMOVED`, `SIGNATURE_CHANGED`, `BEHAVIOR_CHANGED`) has
this "deprecated with nothing to do" ambiguity by construction --
`REMOVED` genuinely has nothing to replace it with, and the rest already
require a target symbol or self-describe a behavior.

### 3-4. Taxonomy corrections

Renamed `multi_hop` → `multi_change`, `single_hop` → `single_change`:
this benchmark covers exactly one version transition (1.10.x → 2.x), so
"hop" language implying a chain of sequential transitions (v2→v3→v4→v5)
was never actually being tested -- these queries combine multiple
changes that co-occur *within* the one transition. True version-path
multi-hop stays explicitly future work, and nothing in the README or
benchmark code claims to test it now.

Split `ambiguous_alias` (4 queries): `q_amb_01` ("What happened to
`parse`?", 3 required changes, genuinely under-specified) keeps a
distinct category, renamed `underspecified_symbol`. `q_amb_02`/`03`/`04`
(each asking about one specific old name, not actually multi-candidate)
renamed `legacy_symbol`. Scope, as instructed: rename only, no broader
taxonomy/schema redesign (e.g. the `query_style`/`change_category`/
`reasoning_pattern` facet split you sketched as a longer-term idea for
`q_config_03`/`q_behav_03` sharing a change_id -- noted as a real
observation, not implemented; that sharing itself is not a bug, per your
own conclusion, since both queries correctly point at the same real
`Field()` fact).

Updated: `generate_pydantic_gold_set.py` (taxonomy values),
`generate_gold_review_checklist.py` (`FLAGGED_TYPES`), README (table
headers, taxonomy explanation, roadmap checklist wording).

### 5-6. `ChangeType.BEHAVIOR_CHANGED`

The enum value already existed (`src/entities/models.py`, since Stage 2/3)
-- it just wasn't being reached, because `BaseModel.__eq__` and the
`dataclasses` tuple-input fact were phrased with keywords
(`change_extraction.py`'s `_CHANGE_TYPE_KEYWORDS`) that route to
`SIGNATURE_CHANGED` ("now requires...", "no longer accepts..."). Fixed by
rephrasing both corpus sentences to use the existing "behavior changed"
keyword instead ("`BaseModel.__eq__` behavior changed in v2.0.0: two
instances only compare equal when..."; "`pydantic.dataclasses` validation
behavior changed in v2.0.0: tuples are no longer accepted..." -- note
"accepted", not "accepts", so the SIGNATURE_CHANGED keyword correctly
doesn't also fire). No change to the keyword table itself, since that
table is shared with `Field()`'s "no longer accepts" fact, which should
stay `SIGNATURE_CHANGED` -- a global keyword remap would have
reclassified that too, which wasn't asked for and isn't obviously right.

**Downstream aggregation audit** (required before treating this as done):
searched every `change_type`/`ChangeType` usage in `src/aggregation/`.
Finding: **no code changes were needed**. `constraints.py`'s
`check_non_overlapping_change_semantics` and `pairwise.py`'s
`change_type_match` signal both operate by pure equality / whitelist-
membership (`config.COMPATIBLE_CHANGE_TYPE_PAIRS`, empty by default) --
neither has any per-type branch anywhere, by design (this is exactly why
`COMPATIBLE_CHANGE_TYPE_PAIRS` exists as an explicit, reviewed, empty-by-
default whitelist: so a new `ChangeType` value is safe by construction,
never silently compatible with anything else). `blocking.py` doesn't
reference `change_type` at all. Confirmed with two new regression tests
(`test_cannot_link.py`, `test_pairwise_resolution.py`): a `BEHAVIOR_CHANGED`
claim and a `SIGNATURE_CHANGED` claim for the same symbol still
cannot-link by default (conservative, as required), and two
`BEHAVIOR_CHANGED` claims still score as a matching pair in pairwise
scoring, same as any other equal-type pair.

### 7. Stability-evidence feasibility (answered before implementing)

1. *Can `Evidence` represent stability without structural change?* No,
   not cleanly -- `Evidence` is Level-1-extraction output (an
   `UnresolvedChange` claim), and a stability fact isn't a change claim,
   so forcing it through that pipeline would need new extraction logic
   (out of scope).
2. *Does the corpus already have enough v2-stable content?* No -- Stage 7's
   corpus was 100% breaking-change facts. Added a new "Stable in v2"
   section to `concepts.md` (5 real, verifiable facts, one bullet each
   -- same per-fact chunking discipline as the changed-facts sections, so
   they don't dilute each other the way the pre-fix `migration_guide.md`
   sections did).
3. *Can `GoldQuery` support `stability_evidence_ids` without changing
   extraction behavior?* Yes -- added as an optional field (default `[]`)
   resolved to **chunk_ids**, not evidence_ids: stability facts never go
   through Level 1 extraction, so there's no Evidence record to point at,
   but chunking already runs independently and needed no changes.
4. *Which negatives are narrow/verifiable?* `q_neg_01` (BaseModel primary
   class), `q_neg_02` (explicit-default field), `q_neg_03` (pip install)
   were already narrow -- kept, just given real stability evidence.
5. *Which are too broad?* `q_neg_04` ("nested BaseModel classes still
   work the same way?") and `q_neg_05` ("Enum field definitions need any
   changes?") -- "same way" and "any changes" aren't provable
   propositions, and the v2.0 release notes (Stage 7 research) actually
   mention *some* internal Enum-handling changes, so "no change" wasn't
   even safely true for `q_neg_05` as originally worded. Rewritten to
   narrow, provable claims: `q_neg_04` → "can a `BaseModel` field still
   be typed as another `BaseModel` subclass?" (existence, not "every
   way"); `q_neg_05` replaced entirely with "is custom field-level
   validation still supported via `@field_validator`?" (a claim the
   corpus can actually back).

Conclusion: cheap and structural-change-free by construction (chunk_id
reference, no extraction pipeline touched) -- implemented per your own
"if cheap, implement" branch. All 5 negative queries now carry a real
`stability_evidence_ids` chunk reference; verified via the gold-set
generator's own consistency check (`missing_stability_facts`), which
would hard-fail the generation run if any text didn't match a real chunk
exactly.

### 8. Version precision (minimal, not full SemVer)

Added `VersionPrecision` (`MAJOR`/`MINOR`/`PATCH`) and a `precision`
field on `VersionMention` in `version_normalization.py`, derived from the
number of numeric components actually present in the source text ("v2"
→ MAJOR, "v2.0" → MINOR, "v2.0.0" → PATCH; "1.2.x" → MINOR, since the
wildcard "x" isn't a real patch number). This is purely additive to the
extraction layer -- no ordering/comparison operators defined over it, and
`intervals_overlap()` in `retrieval/version_filter.py` is deliberately
untouched (padding mismatched-length version-key tuples for *comparison*
is a different concern from what precision a claim *asserts*, and that
padding fix already shipped in Stage 7). Not propagated into the
persisted `ChangeRecord` schema this pass -- that would be a second
schema migration with its own blast radius, recorded here as deferred,
not silently skipped.

The concrete complaint (`BaseModel.parse_file`'s `version_to="2"` sitting
inconsistently next to siblings' `"2.0.0"`) is separately resolved as a
side effect of § 2B's corpus rewrite (the bare "v2" phrasing that caused
it is gone). Full SemVer interval algebra, prerelease ordering, wildcard
ranges, and `[2.0.0, 3.0.0)`-style representation are explicitly deferred,
per your scope instruction -- recorded as technical debt, not implemented.

### 10-11. Rebuild and full test suite

Rebuilt from scratch (`build_pydantic_benchmark_corpus.py`): 3 documents
→ 76 chunks (was 70; +6 for the new "Stable in v2" bullets and the split
to_camel/to_lower_camel fact) → 34 `UnresolvedChange` claims (was 33) →
27 `ChangeRecord`s (was 26; +1 net) → 0 cannot-link vetoes. Regenerated
the gold set (`generate_pydantic_gold_set.py`) against the fresh DB --
all 48 queries resolved with zero missing symbols and zero missing
stability facts (the generator hard-fails on either, so this is a real
verification, not an assumption).

Full suite: **147 passed** (up from 140; +7 Stage-8A regression tests:
2 `BEHAVIOR_CHANGED` cannot-link/pairwise tests, 1 `MOVED`-pattern
extraction test, 4 `VersionPrecision` tests), same **5 pre-existing**
`test_retriever.py`/`test_vector_store.py` failures, untouched as
instructed.

### 12-13. Benchmark re-run and failure diagnosis vs. `8e540dc`

See README's "Benchmark Results" section for the full tables (change-
level and evidence-level, all four modes, per-query-type slice). Summary:

| | Dense R@5 | BM25 R@5 | Hybrid R@5 |
|---|---|---|---|
| `8e540dc` (pre-correction) | 0.927 | 0.844 | 0.958 |
| post-remediation | 0.948 | 0.844 | 0.938 |

Hybrid's Recall@5 went **down** (0.958 → 0.938) and Dense's went up
slightly; Hybrid no longer has the top Recall@5 in this run (though it
still leads on MRR/nDCG@5: 0.799/0.808 vs Dense's 0.786/0.793). Per your
own review principle (§9E: correct labels over attractive scores) this is
reported as-is, not chased. The mechanism is examined in README's new
"Hybrid does not strictly dominate Dense" section: `q_nl_03` is the clean
example -- Dense finds `BaseModel.parse_obj` at rank 4 (top-5 hit) on its
own, BM25 never finds it, and the *actual* RRF fusion pool the benchmark
uses (top_k=10 → 40 fused candidates, reconstructed exactly for this
diagnosis) ranks it 11th. RRF sums per-list rank credit; a chunk BM25
never touches gets zero credit from that side and can be out-accumulated
by chunks both retrievers rank only moderately.

**Methodology fix caught during this re-diagnosis, worth recording**: an
earlier draft of the failure-diagnosis script called `retrieve_hybrid()`
with `top_k=50` to "look deeper," not realizing `retrieve_hybrid`'s RRF
candidate pool (`fetch_k = top_k * 4`) scales with whatever `top_k` the
caller passes -- so a `top_k=50` call fuses a *different, larger* pool
than the real benchmark's `top_k=10` call, and can produce a materially
different fused ranking for the same query (confirmed concretely:
`q_multi_02` showed a rank-6/7 near-miss under the wide diagnostic pool
but is a clean full pass, recall@5=1.0 on every mode, under the real
benchmark's actual pool -- the wide-pool number was simply wrong for
answering "did the real benchmark call fail"). Fixed by making
`scripts/diagnose_failed_queries.py` (a) read
`data/benchmark/per_query_results.csv` as the authoritative source for
*which* queries fail, never re-derive it independently, and (b)
reconstruct Hybrid's rank at the *exact* fetch_k the real benchmark used,
not a bigger ad hoc pool. Dense/sparse ranks don't have this problem
(no fusion, so requesting more results doesn't reorder ones already
returned).

**Failure classification, authoritative** (3 non-negative queries with
real Hybrid Recall@5 < 1.0):

| Query | Dense rank | Sparse rank | Hybrid rank (real pool=40) | Class |
|---|---|---|---|---|
| `q_nl_02` | 20/50 | not found | 35/40 | RANKING |
| `q_nl_03` | 4/50 (top-5!) | not found | 11/40 | RANKING |
| `q_amb_01` | 23-25/50 (best of 3) | not found | 30-33/40 | UNDERSPECIFIED_SYMBOL |

No CORPUS_GAP, EXTRACTION_GAP, LABEL_ERROR, or VERSION_FILTER_ERROR among
these three -- all three facts are demonstrably extracted and indexed
(Dense finds all of them within the top 25 of 76 chunks), the labels were
specifically re-verified this stage, and `hybrid_version_filtered`'s
numbers track plain `hybrid` closely throughout with no traceable
distortion. Per your instruction, not defaulting any of these to "needs
agentic decomposition" -- two are RANKING (reranker candidate), one is
UNDERSPECIFIED_SYMBOL (context/symbol-expansion candidate), and none are
addressed in Stage 8A itself.

### 14. Review checklist v2

Regenerated `data/gold/pydantic_gold_review_checklist.md` against the
corrected live corpus: adds an explicit "Migration action: use `X`" line
per required change (or a note that it's a status-only fact with a
pointer to `deprecated_action_audit.md` when no action exists), a
`stability_evidence_ids` section for negative queries, and updated
`FLAGGED_TYPES` (`multi_change` / `underspecified_symbol` /
`behavioral_change` / `negative`). Not auto-declaring anything frozen --
that stays your call.

### 15. Documentation

README's Benchmark Results section rewritten with the corrected tables,
the "Hybrid does not strictly dominate Dense" finding, the corrected
failure classification table, an explicit "`multi_change` is not
version-path multi-hop" disclaimer, and the version-filter/config-change/
behavioral-change limitation notes carried forward accurately. Project
Status checklist updated (Stage 8A items marked done, gold-set sign-off
moved to "in progress" rather than implied-complete). This log entry is
that documentation's counterpart for implementation-level detail.

### Not done (explicitly out of scope, confirmed against your exclusion list)

Reranker, query decomposition/rewrite/context expansion, LangGraph,
adaptive retrieval, LLM extraction fallback, Late Chunking, new embedding
model, Qdrant migration, full SemVer interval engine, new stability-
extraction pipeline, executable code migration, automatic patch
generation, the five pre-existing legacy retriever/vector-store test
failures, and the `query_style`/`change_category`/`reasoning_pattern`
facet redesign (recorded as a good idea for later, not built).

**Gold set status: corrected, self-consistent, and re-verified against
real pipeline output -- not yet declared v1.** Freeze remains your call,
same as before this remediation pass.
