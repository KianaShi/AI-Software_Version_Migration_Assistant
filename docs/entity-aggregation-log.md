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

## Stage 8A.1 — Second-round Gold Set cleanup (your review of checklist v2)

You reviewed checklist v2 against the official pydantic migration docs a
second time and found the Stage 8A fixes were correct but incomplete: 5
more issues that would still pollute freeze-quality evaluation. This
section is that cleanup. Baseline: commit `6b89d9b`.

### 1. `migration_action_text` -- status-only facts that actually had an action

You found that `q_behav_02`/`q_behav_03`/`q_config_03` and the
`GenericModel`/`ConstrainedStr` facts all had a real recommended action
sitting right in their own evidence text ("use dicts instead", "use the
`json_schema_extra` parameter instead", "subclass `BaseModel` and
`Generic` directly instead", "use `Annotated` with `Field` constraints
instead") that never made it into `replacement_symbol`, because
`change_extraction.py`'s single-symbol keyword path (as opposed to the
replacement-pattern fast path) never populated it at all. Your call: don't
force these into `replacement_symbol` (not every migration is a clean
1:1 symbol rename), add a separate free-text field instead.

Added `ChangeAttributes.migration_action_text: str | None` (schema +
`store.py` column + `linker.py` threading, same additive pattern as
`replacement_symbol`/`parameters`). Extraction: a new
`_ACTION_CLAUSE_RE` in `change_extraction.py` captures a trailing
`"; ... instead[.]"` clause generically, applied inside `_build_change()`
so it fires regardless of which extraction path produced the statement
-- not a new keyword-table entry (that table is shared with `Field()`'s
"no longer accepts", which should stay `SIGNATURE_CHANGED`; a global
remap would have reclassified things nobody asked to reclassify). All 4
facts you flagged now populate it correctly; verified directly against
the rebuilt DB, not just by re-reading the regex. 3 new regression tests.

### 2. `NoneStr` action + `stricturl` query

`NoneStr` really is a documented alias for `None | str` -- corpus updated
to state that and add "use `str | None` instead" (captured via the same
action-clause regex). `stricturl` has no 1:1 replacement in the official
guide; per your explicit principle (don't manufacture facts), the corpus
stays status-only for it, and the *query* changed from "what do I need
to change" (implies an action exists) to "Was `pydantic.stricturl`
removed in v2?" (doesn't).

### 3. Overstated wording in `q_behav_01` / `q_behav_03`

`q_behav_01`'s corpus fact said non-equal-type models "share the exact
same type" unconditionally -- true for non-generic models, but generic
models allow some same-origin cases, so this overstated the real rule.
Narrowed corpus fact and query to "non-generic models" specifically.
`q_behav_03`'s query claimed `Field()` "raises a validation error" on
extra kwargs -- the evidence only supports "unsupported, use
`json_schema_extra` instead," not a specific exception type. Query
reworded to not claim what isn't verified. Corpus text itself was already
fine in both cases; only the gold query text overstated things.

### 4. `q_neg_05` wasn't a valid negative

Old query ("is custom validation still supported?") had
`required_change_ids=[]` but its own `stability_evidence_ids` said
"...only the decorator name changed from v1's `@validator`" -- that's
*capability preserved, API migration required*, not *no migration
change*. Scoring it as a clean negative would have polluted the
negative-set's real purpose (testing against over-warning). Per your
guidance, not worth a new taxonomy value (`capability_preserved_with_migration`)
for one query -- replaced entirely with a clean, narrow, unconflated
claim: "Do I still access individual field values as plain attributes
(e.g. `model.field_name`) in pydantic v2?", backed by a new, real,
unconflated "Stable in v2" bullet. The old `@field_validator` stability
bullet was removed from `concepts.md` rather than left dangling, since it
had the identical conflation problem baked into the corpus fact itself,
not just the query.

### 5. `q_amb_01` excluded from the core retrieval aggregate

Added `GoldQuery.evaluation_scope` (default `"retrieval"`;
`"query_planner"` for `q_amb_01`). Its 3-symbol required set is an
editorial choice about what an underspecified query "should" mean --
there's no single correct retrieval target, so scoring it in the main
Dense/BM25/Hybrid Recall@K table penalizes retrieval for a question
without one gold interpretation. `run_pydantic_benchmark.py` now filters
`evaluation_scope != "retrieval"` queries out of the core aggregate/
per-type/CSV, and reports them in a separate section instead (still
computed, still visible, just not folded into the headline numbers).
`underspecified_symbol` as a *taxonomy* label is unchanged and still
correct per your Stage 8A judgment -- this is an orthogonal scoring-scope
flag, not a taxonomy redesign, so it doesn't reopen the "don't expand
taxonomy this stage" boundary.

### Rebuild, tests, re-run

Rebuild: same 76 chunks / 34 `UnresolvedChange` / 27 `ChangeRecord`s as
before (these edits rephrased/completed existing facts, not added new
distinct ones). Full audit re-run
(`data/gold/deprecated_action_audit.md`): of 15 `DEPRECATED`/`MOVED`/
`REMOVED`-plus-flagged records, 14 now carry a real action, 1
(`stricturl`) intentionally doesn't. Regenerated the gold set (all 48
resolve cleanly, zero missing symbols/stability facts) and checklist v3
(now shows `migration_action_text` and `evaluation_scope` per query).

Full suite: **150 passed** (+3: action-clause extraction, no-action-clause
control, linker threading), same 5 pre-existing failures, untouched.

Benchmark re-run, core aggregate now over 47 queries (`q_amb_01`
reported separately): Dense R@5 0.968, BM25 0.830, Hybrid 0.957, Hybrid+
version-filter 0.936. Only 2 core-scope queries remain below Recall@5=1.0
under Hybrid (`q_nl_02`, `q_nl_03`), both re-classified RANKING with the
same pool-size-consistent methodology from Stage 8A (dense finds both
within top 20, hybrid's real 40-candidate fusion pool ranks them lower).
`q_amb_01` alone: 0.000 across all four modes, classified
UNDERSPECIFIED_SYMBOL, excluded from the headline table as described
above. See README's Benchmark Results section for full tables.

**Files added**: none new (this stage extended existing files).

**Files modified**: `src/entities/models.py` (`migration_action_text`
field), `src/entities/store.py` (schema/row-mapping), `src/aggregation/linker.py`
(threading), `src/extraction/change_extraction.py` (`_ACTION_CLAUSE_RE`),
`src/retrieval/evaluation.py` (`evaluation_scope` field on `GoldQuery`),
`data/corpus/pydantic/migration_guide.md` (NoneStr action,
`__eq__` narrowed to non-generic), `data/corpus/pydantic/concepts.md`
(`q_neg_05` stability fact swapped), `scripts/generate_pydantic_gold_set.py`
(query wording, `stricturl`/`q_neg_05` changes, `evaluation_scope`),
`scripts/generate_gold_review_checklist.py` (checklist v3 fields),
`scripts/run_pydantic_benchmark.py` (core-vs-scoped-out split),
`data/gold/deprecated_action_audit.md` (re-audited), README, this log,
plus 3 new regression tests.

**Gold set status: corrected twice now, self-consistent, re-verified --
still not declared v1.** Waiting on your final pass over checklist v3
and `deprecated_action_audit.md` before that decision, exactly as before.

## Stage 8A.2 — Scope split, gold set metadata, final wording pass

You reviewed checklist v3 and confirmed the content fixes were now
correct, but asked for four more structural/scope/wording changes before
you'd consider re-running the benchmark as the real baseline. You were
explicit up front: whatever Dense/BM25/Hybrid come out to after these
four, you won't keep revising gold based on score. Baseline: commit
`d549883`.

### 1-2. Three-way `evaluation_scope`, 42-query core, gold set metadata

Split `evaluation_scope` from binary (`retrieval`/`query_planner`) into
three values: `change_retrieval` (42 queries -- the core aggregate),
`stability` (the 5 negatives -- `required_change_ids` is always
vacuously empty, so change-level Recall@K is trivially 1.0 for them
regardless of retrieval quality, which was quietly propping up the
Stage 8A.1 47-query aggregate with 5 free 1.0s that measured nothing),
and `query_planner` (unchanged, `q_amb_01`). `run_pydantic_benchmark.py`
now filters to `change_retrieval` for the core aggregate/per-type/CSV
and reports `stability` and `query_planner` in two separate labeled
sections instead of one combined "scoped out" bucket.

Added a `metadata` block to the gold JSON itself (previously a bare
array; now `{"metadata": {...}, "queries": [...]}`) --
`name: "Pydantic Gold Set v1"`, `migration_scope: "1.10.x -> 2.x"`,
`review_revision: 3`, `status: "pending_freeze"`, `source_commit: null`.
`status`/`source_commit` are deliberately left unset here: this script
never declares the gold set frozen itself, and `source_commit` has an
inherent chicken-and-egg problem (the commit that introduces a value
can't contain its own hash) -- both get filled in only at the actual
freeze moment, a separate explicit action, exactly matching your own
stated pipeline (commit → human freeze, not the same step). Updated all
four scripts that read the gold JSON (`run_pydantic_benchmark.py`,
`generate_gold_review_checklist.py`, `diagnose_failed_queries.py`,
plus the generator itself) for the new `{"metadata", "queries"}` shape.

### 3. Wording tightened, semantics clarified

`q_neg_01`/`q_neg_02` reworded to mirror their stability evidence text
closely (`"still exist as the main way"` → `"still the primary way"`,
`"still work the same way"` → `"still behave the same way"`) rather than
a looser paraphrase that technically claimed slightly more than the
evidence states.

Added a "Field semantics" section to `deprecated_action_audit.md`:
`replacement_symbol` names what to call, not a guarantee the migration
is purely mechanical -- `BaseModel.from_orm` → `model_validate` is
correct as a pointer, but the complete action also requires enabling
`from_attributes` on `model_config` first, which lives in the evidence
`raw_text`, not in the field itself. Documented so a future consumer
(human or LLM) doesn't treat `replacement_symbol` alone as "the entire
diff."

### Rebuild, tests, re-run

Full suite: **150 passed** (no new tests this round -- purely structural/
scope/wording changes, no new extraction behavior to lock in). Same 5
pre-existing failures, untouched.

Gold set regenerated: 48 queries, `evaluation_scope` distribution
42/5/1 (`change_retrieval`/`stability`/`query_planner`) exactly as
designed. Benchmark re-run, core aggregate now over 42 queries (the 5
trivially-1.0 negatives no longer inflate it):

| | Dense | BM25 | Hybrid | Hybrid+vf |
|---|---|---|---|---|
| Recall@5 | 0.964 | 0.810 | 0.952 | 0.929 |
| MRR | 0.889 | 0.766 | 0.875 | 0.863 |

Only 2 of 42 queries remain below Recall@5=1.0 under Hybrid (`q_nl_02`
fails under every mode, `q_nl_03` only under Hybrid) -- both
re-classified RANKING with the same pool-size-consistent methodology
from Stage 8A.1. No new failure categories surfaced; this round changed
scope/wording/metadata, not facts, so no new content-level findings were
expected and none appeared.

**Files modified**: `scripts/generate_pydantic_gold_set.py` (evaluation_scope
rename+split, `GOLD_METADATA`, wording), `scripts/run_pydantic_benchmark.py`
(metadata-aware `load_gold()`, 3-way scope split, separate reporting),
`scripts/generate_gold_review_checklist.py` (metadata-aware loading,
header), `scripts/diagnose_failed_queries.py` (metadata-aware loading),
`src/retrieval/evaluation.py` (`evaluation_scope` default renamed),
`data/gold/deprecated_action_audit.md` (semantics note), README.

**Gold set status: corrected three times now, self-consistent, matches
the numbers you said you'd accept regardless of which retriever wins.**
Still not declared frozen -- per your own pipeline, that's the next,
separate step, on your side.

## Gold Set v1 FROZEN

You confirmed the Stage 8A.2 checklist and numbers, and made the freeze
call. Isolated metadata-only commit `bb9efc8` (deliberately separate from
the Stage 8A.2 content commit, per your instruction): `GOLD_METADATA` in
`scripts/generate_pydantic_gold_set.py` updated to
`status: "human-reviewed / frozen"`, `source_commit: "33163fd"` (the
last content commit -- the actual snapshot you reviewed; this freeze
commit's only job is to label that snapshot frozen, not change it --
avoids the self-referencing-hash problem entirely, as you pointed out).
Added `gold_set_version: "1"` as the externally-referenced release
identifier, distinct from `review_revision` (which stays as the internal
count of correction rounds: 3, Stage 8A → 8A.1 → 8A.2). Regenerated the
gold JSON via the script (not hand-edited) and confirmed via `git diff`
that only the `metadata` block changed -- the 48 `queries` are
byte-identical to `33163fd`, exactly as expected since nothing about the
underlying facts changed in this step. Tagged `pydantic-gold-v1`
(annotated). README and this log updated to reflect frozen status in a
separate, still-small follow-up commit.

**Rule in effect starting now, stated explicitly by you and recorded
here so it isn't relitigated later**: Stage 8B does not modify Gold Set
v1 to make retrieval scores look better. If an experiment underperforms
against the frozen baseline below, the fix is to change retrieval, not
the gold set. Reopening the gold set requires a real factual error,
wrong evidence, wrong `required_change_id`, or an invalid query --
never a low score -- and any such reopening becomes a new revision
(v1.1/v2), never a silent edit to v1.

**Frozen baseline** (42-query `change_retrieval` core, commit `33163fd`,
reproducible via `python -m scripts.build_pydantic_benchmark_corpus` →
`generate_pydantic_gold_set` → `run_pydantic_benchmark`):

| | Dense | BM25 | Hybrid | Hybrid+vf |
|---|---|---|---|---|
| Recall@5 | 0.964 | 0.810 | 0.952 | 0.929 |
| MRR | 0.889 | 0.766 | 0.875 | 0.863 |

Dense > Hybrid > BM25 on Recall@5, and naive 1:1-weighted RRF fusion does
not improve on a strong Dense retriever here -- a real, examined finding
(see README "Hybrid does not strictly dominate Dense"), not an artifact
of an uncorrected gold set. The two remaining failures point at two
distinct next steps, not one:

- `q_nl_02` -- fails under every mode (Dense included, rank 20/50) →
  candidate/semantic ranking problem → reranker.
- `q_nl_03` -- Dense succeeds (rank 4, clean top-5), Hybrid fails (real
  fusion pool rank 13/40) → fusion dilution problem, not a ranking-model
  problem → fusion/weighting ablation, or reranker over the union of
  candidates rather than the fused list.

**Not done, per your explicit instruction to stop here**: no Stage 8A.3.
Next is Stage 8B0 (fixed candidate-pool / output-k evaluation protocol)
when you say go -- not started as part of this freeze.

## PR review fix — CodeRabbit findings on `stage8a-gold-freeze`

Branch pushed, tag `pydantic-gold-v1` pushed, PR opened against `main`.
CodeRabbit reviewed and found three real problems in the tooling *around*
the frozen artifact, not in the frozen artifact itself. You triaged all
three as in-scope for this PR (not score-chasing, not algorithm changes)
and this section is that fix, landed as a single small commit on the
same branch -- the `pydantic-gold-v1` tag was not moved; it still points
at `bb9efc8`.

**1. Checklist stale (`pending_freeze`) -- MUST FIX.** The gold JSON's
`status` was updated to `human-reviewed / frozen` at freeze time, but
`data/gold/pydantic_gold_review_checklist.md` was never regenerated
afterward, so the checked-in review artifact contradicted the source of
truth it's supposed to reflect. Fix: no hand-edit -- reran
`scripts/generate_gold_review_checklist.py`, which reads `status`
straight from the JSON metadata, so the header now shows
`` Status: `human-reviewed / frozen` `` correctly.

**2. `change_retrieval` mislabeled excluded -- MUST FIX, same root cause
as CodeRabbit's checklist comment.** `generate_gold_review_checklist.py`
still compared `evaluation_scope` against the pre-Stage-8A.2 value
`"retrieval"` (`scope = q.get("evaluation_scope", "retrieval")`), but the
real core-scope value has been `"change_retrieval"` since Stage 8A.2 --
so every one of the 42 core queries was incorrectly annotated
"excluded from core Recall@K aggregate" in the checklist, directly
contradicting the frozen benchmark's own definition of its core
aggregate. Fixed the default and comparison to `"change_retrieval"`;
regenerated. Verified by grep count on the regenerated file: 0 core
queries carry the excluded-suffix note, 5 `stability` and 1
`query_planner` do (exactly the 42/5/1 split).

**3. Frozen Gold JSON could be silently overwritten by the generator --
VALID, fixed with a minimal guard, not a version-management system.**
The documented rule ("Stage 8B does not modify Gold Set v1") was policy
only -- nothing in `generate_pydantic_gold_set.py` actually enforced it.
Added `query_digest()`: a canonical SHA256 over the *resolved queries
list only* (`json.dumps(..., sort_keys=True, separators=(",", ":"))`),
deliberately excluding `GOLD_METADATA` so freeze-status/source_commit
edits never perturb it. `FROZEN_V1_QUERY_DIGEST` is the digest computed
once from the currently-frozen 48-query payload
(`ae8cadf25b2005b46...bff44f8`). `check_frozen_guard(gold_metadata,
generated_queries)` -- extracted as its own function specifically so it
has direct unit tests, not just an inline check buried in `main()` --
raises `RuntimeError` if `status == "human-reviewed / frozen"` and the
freshly generated digest doesn't match. A real future correction still
works exactly as documented: bump `review_revision`/`gold_set_version`
and update `FROZEN_V1_QUERY_DIGEST` deliberately: silent drift is what's
blocked, not a real, explicit reopening.

**Files modified**: `scripts/generate_gold_review_checklist.py` (scope
default/comparison fix), `scripts/generate_pydantic_gold_set.py`
(`query_digest`, `FROZEN_V1_QUERY_DIGEST`, `check_frozen_guard`),
`data/gold/pydantic_gold_review_checklist.md` (regenerated).

**Files added**: `tests/test_gold_set_generation.py` (6 tests: digest
determinism across key order, digest sensitivity to content drift, guard
passes on matching digest, guard raises on drift, guard no-ops when not
frozen, and `test_current_frozen_gold_queries_match_committed_digest`,
which checks only that the *checked-in* `pydantic_gold_queries.json`
still hashes to `FROZEN_V1_QUERY_DIGEST` -- it reads the committed
artifact directly and does **not** run `GOLD_QUERIES`/`NEGATIVE_QUERIES`
through the resolution pipeline, so it cannot by itself catch someone
editing those definitions in the script. That drift is instead caught
at generation time: `main()` resolves the definitions into `gold` and
calls `check_frozen_guard(GOLD_METADATA, gold)` before the file is ever
written, so a source-level edit either fails loudly there or the
resulting JSON simply wouldn't match what's committed -- a full
`run_pipeline()` integration test asserting this end-to-end was
considered and deliberately left out of this PR as more than the fix
needed).

**Verification, no benchmark rerun**: retrieval algorithms and the gold
query payload are both untouched by this fix (confirmed: `git diff` on
`data/gold/pydantic_gold_queries.json` is empty after regenerating it
through the guarded generator -- the digest check passing *is* that
proof), so there's no reason the frozen baseline numbers would move.
Instead ran an integrity check: digest match confirmed, 42/5/1 scope
split unchanged, full suite 156 passed (150 prior + 6 new) with the same
5 pre-existing unrelated `test_retriever.py`/`test_vector_store.py`
failures, untouched as always.

## PR review fix, round 2 — CodeRabbit findings on the round-1 fix commit

Second CodeRabbit pass reviewed `01e5825` itself and found two more
issues. Both verified against current code before fixing; both were
real.

**1. Overstated claim about what the digest regression test covers.**
`test_current_frozen_gold_queries_match_committed_digest` reads
`data/gold/pydantic_gold_queries.json` straight off disk and checks it
against `FROZEN_V1_QUERY_DIGEST` -- it never touches `GOLD_QUERIES`/
`NEGATIVE_QUERIES` or runs them through the resolution pipeline, so the
log's claim that it "fails the day someone edits GOLD_QUERIES/
NEGATIVE_QUERIES" was wrong: editing those definitions and rerunning the
generator is what `check_frozen_guard()` inside `main()` catches
(pre-write, before the JSON file changes at all) -- this test only
catches the file being hand-edited or the guard being bypassed. Doc
corrected above to describe the actual coverage split. Per your
instruction, not adding a full `run_pipeline()` integration test in this
PR -- `check_frozen_guard()` already has direct unit coverage, and an
end-to-end test through the real pipeline is more machinery than this
fix needs.

**2. `evidence_links` query had no `ORDER BY`.** The
`SELECT change_id, evidence_id FROM evidence_links` populating
`change_to_evidence_ids` relied on SQLite's unspecified row order for an
unindexed scan -- harmless today, but `relevant_evidence_ids` is a list
(digest-sensitive to element order, unlike the dict-key ordering
`query_digest()` already normalizes via `sort_keys=True`), so a future
DB engine/index/SQLite-version change could silently reorder it and trip
the frozen-guard on a rebuild that changed nothing real. Added
`ORDER BY change_id, evidence_id`. Regenerated through the guarded
generator: digest matched (guard didn't raise), and `git diff` on
`data/gold/pydantic_gold_queries.json` was empty -- the implicit order
was already correct, this just stopped relying on an unspecified
guarantee for it.

**Files modified**: `scripts/generate_pydantic_gold_set.py` (`ORDER BY`
on the `evidence_links` query), `docs/entity-aggregation-log.md` (this
entry + corrected description of the digest test's coverage).

**Verification**: frozen gold JSON byte-identical (empty diff), full
suite 156 passed, same 5 pre-existing unrelated failures. No benchmark
rerun (retrieval code and gold payload both untouched), tag
`pydantic-gold-v1` not moved (still `bb9efc8`).

## Stage 8B0 — Decouple candidate_k from output_k in retrieval

Scope, as instructed: fix the retrieval evaluation protocol only --
`candidate_k` (how many ranked candidates are fetched/fused before
filtering) made independent of `output_k` (how many of those survive as
the final result), so Top5/Top10/Top20 are guaranteed nested prefixes of
one ranking. Explicitly excluded and untouched: reranker, RRF weighting
(`RRF_K` still 60, no per-source weight), chunking, query rewriting, and
Gold Set v1 (still frozen at `bb9efc8`, `pydantic-gold-v1` tag not
moved).

**The bug, restated precisely**: `retrieve_dense`/`retrieve_sparse`/
`retrieve_hybrid` used to compute `fetch_k = top_k * 4`, so a single
`top_k` argument controlled both how many candidates were pulled *and*
how many were returned -- calling the same retriever with `top_k=5` vs.
`top_k=10` queried genuinely different candidate pools, not just
different slice lengths of one pool. This is provably harmless for Dense
and Sparse alone: each is a single deterministic ranking, and widening
the fetch only appends lower-ranked candidates after the ones a narrower
fetch already had, so post-filter re-ranking never reorders the shared
prefix. It is **not** harmless for Hybrid: RRF only assigns a nonzero
score to a chunk that appears in at least one of the two fetched
rankings, so a chunk absent from a narrower pool contributes zero credit
from that side; admitting it at a wider pool can let it out-accumulate
chunks that were already ranked near the top of the narrower pool's
fused result -- not merely extend the list, reorder it. This is the
exact mechanism documented in Stage 8A behind `scripts/
diagnose_failed_queries.py`'s manual fetch_k reconstruction (the
`q_multi_02` false-negative under a wider diagnostic pool). Before this
stage, that reconstruction workaround was necessary precisely because
the production API had no way to ask for "the same candidate pool, sliced
differently" -- Top5 and Top10 from two separate calls were not
comparable at all.

**Fix**: `src/retrieval/retrieval.py` -- new module constant
`CANDIDATE_K = 40`, and all three `retrieve_*` functions now take
`output_k` (default 10, was `top_k`) and `candidate_k` (default
`CANDIDATE_K`) as independent parameters. Every call fetches/fuses over
exactly `candidate_k` candidates regardless of `output_k`; `output_k`
only slices the already-computed, already-filtered result at the end.
Because the underlying ranked-and-filtered list no longer depends on
`output_k` at all, `output_k=5`/`10`/`20` against the same `candidate_k`
are guaranteed prefixes of each other by construction of list slicing --
not something that needs re-verifying per query, just a property of the
code shape. Added `_check_output_k()`: raises `ValueError` if
`output_k > candidate_k`, since silently truncating below the requested
depth would be a worse failure mode than refusing.

`CANDIDATE_K = 40` was chosen to exactly match the old effective pool
size at the benchmark's `top_k=10` (`10 * 4 = 40`), specifically so this
refactor is a pure architecture fix, not a silent behavior change to the
frozen baseline -- confirmed below.

**Call sites updated** (mechanical rename + explicit `candidate_k`,
no behavior change intended):
- `scripts/run_pydantic_benchmark.py`: `TOP_K` renamed `OUTPUT_K`
  (still 10); `make_run_query()`'s three `retrieve_*` calls pass
  `output_k=OUTPUT_K, candidate_k=CANDIDATE_K` explicitly (imported from
  `retrieval.py`, so this runner can't silently drift from what
  retrieval.py actually uses).
- `scripts/diagnose_failed_queries.py`: this script's entire reason for
  manually reconstructing Hybrid's fused ranking via direct
  `query_dense`/`query_sparse`/`reciprocal_rank_fusion` calls was to work
  around the old pool-size-follows-top_k coupling. With `candidate_k`
  now fixed independent of `output_k`, that workaround is unnecessary --
  simplified `hybrid_rank_at_benchmark_pool_size()` to call
  `retrieve_hybrid(..., output_k=CANDIDATE_K)` directly through the
  public API and read off the real candidate pool, removing the
  duplicated fusion logic entirely. `_FETCH_MULTIPLIER` no longer exists
  (this script imported it directly, so this fix was required, not
  optional); deep-look `retrieve_dense`/`retrieve_sparse` calls
  (previously `top_k=50`) now pass `output_k=50, candidate_k=50`
  explicitly, since 50 exceeds the new default `candidate_k=40`.
- `tests/test_retrieval_integration.py`: `top_k=` renamed `output_k=` at
  all call sites (mechanical, no assertions changed).

**New regression tests**: `tests/test_retrieval_prefix_stability.py` (8
tests) -- a 25-chunk corpus sharing the query's terms (so Dense and BM25
both return >=20 non-zero candidates), asserting for each of
Dense/Sparse/Hybrid that `output_k=10` results are exactly
`output_k=20`'s first 10, and `output_k=5` is exactly `output_k=10`'s
first 5 -- including for Hybrid, the exact case that was broken before
this stage. Also covers: `output_k > candidate_k` raises `ValueError`
for all three retrievers; `CANDIDATE_K == 40`; explicitly widening
`candidate_k` allows a deeper `output_k` than the default.

**Verification that the frozen baseline didn't move**: reran
`scripts/run_pydantic_benchmark.py` against the fixed retrieval code.
Aggregate numbers are byte-identical to the frozen baseline -- Dense
R@5=0.964/MRR=0.889, BM25=0.810/0.766, Hybrid=0.952/0.875,
Hybrid+vf=0.929/0.863 -- and `git diff --stat data/benchmark/` is empty
(all three CSVs unchanged), confirming this was purely an architecture
fix at `output_k=10` (`candidate_k=40` exactly reproducing the old
`fetch_k` at that one value), not a retrieval-quality change. Full test
suite: 164 passed (156 prior + 8 new), same 5 pre-existing unrelated
`test_retriever.py`/`test_vector_store.py` failures, untouched.

**Files modified**: `src/retrieval/retrieval.py` (`candidate_k`/
`output_k` decoupling, `CANDIDATE_K`, `_check_output_k`),
`scripts/run_pydantic_benchmark.py` (`OUTPUT_K` rename, explicit
`candidate_k`), `scripts/diagnose_failed_queries.py` (simplified via the
new public API, `_FETCH_MULTIPLIER` import removed),
`tests/test_retrieval_integration.py` (`top_k=` → `output_k=`).

**Files added**: `tests/test_retrieval_prefix_stability.py`.

**Not done, per this stage's explicit scope**: no reranker, no RRF
weight/`RRF_K` tuning, no Gold Set v1 changes, no chunking changes, no
query rewriting. Gold Set v1 remains frozen and untouched; benchmark
numbers confirmed unchanged, not re-optimized.

## PR #2 review fix — `_check_output_k` didn't validate `candidate_k`/`output_k` themselves

CodeRabbit found `_check_output_k` only checked `output_k > candidate_k`,
never validating that either value was sane on its own. Verified: real
bug, not just a defensive nitpick. `query_dense`/`query_sparse` compute
`n = fetch_k or top_k` -- `fetch_k=0` is falsy in Python, so
`candidate_k=0` would silently fall through to that function's own
`top_k=10` default instead of an empty pool, which is exactly the
"candidate pool secretly depends on something other than candidate_k"
failure mode this whole stage exists to prevent. A negative `output_k`
had no guard either (Python's `list[:-1]` silently drops the last
element rather than erroring). Fixed: `_check_output_k` now rejects
`candidate_k <= 0` and `output_k < 0` before the existing
exceeds-candidate_k check. Added `tests/
test_retrieval_prefix_stability.py::test_candidate_k_zero_or_negative_raises`
and `::test_output_k_negative_raises` (parametrized over Dense/Sparse/
Hybrid, 6 new tests). Also fixed a nitpick in the same file: an unused
`sparse_index` binding in `test_widening_candidate_k_explicitly_allows_deeper_output_k`
renamed to `_`.

**Verification**: full suite 170 passed (164 prior + 6 new), same 5
pre-existing unrelated failures. Reran the frozen benchmark: numbers
unchanged (Dense 0.964/0.889, BM25 0.810/0.766, Hybrid 0.952/0.875,
Hybrid+vf 0.929/0.863), `git diff --stat data/benchmark/ data/gold/`
empty -- the new validation only rejects invalid input, the valid path
(`output_k=10, candidate_k=40`) is untouched.

**Files modified**: `src/retrieval/retrieval.py` (`_check_output_k`
guards), `tests/test_retrieval_prefix_stability.py` (2 new parametrized
tests, unused-variable nitpick fix).

## PR #2 — DeepSource `PYL-E1120` triage (not fixed here)

DeepSource flagged 4 occurrences of `PYL-E1120` ("no value for argument")
in `tests/test_retriever.py:20` and `tests/test_vector_store.py:31` --
calls to `add_chunks()` missing `chunks`/`embeddings`/`metadatas`. These
are exactly the 5 pre-existing `test_retriever.py`/`test_vector_store.py`
failures documented since Stage 4 (legacy interface mismatch, neither
file touched by any stage in this log): not a regression introduced by
Stage 8B0 (this PR never touches `src/retriever.py` or
`src/vector_store.py`'s legacy call sites), and not a false positive
either -- the calls genuinely don't match the current `add_chunks()`
signature.

**Triage, your call**: VALID finding / OUT OF SCOPE for Stage 8B0 /
EXISTING TECH DEBT. Not fixed in this PR -- fixing it here would pull an
unrelated pre-existing issue into a PR scoped to `candidate_k`/`output_k`
decoupling. Left as the same "pre-existing, unrelated" note carried
since Stage 4, now with a DeepSource ticket number attached to it for
traceability.

**Tightened policy going forward, stated explicitly so it isn't
relitigated**: "leave the 5 known failures alone indefinitely" stops
being the right call the moment there's real work to do near this code
-- a clean `164 passed, 5 known failures` baseline degrades over time
into "is this new failure one of the 5 old ones or a real regression?"
requiring manual triage every time. Before Stage 8B1 starts, a small,
separately-scoped **repository-health-audit** step (not part of 8B0,
not part of 8B1's retrieval work) will resolve `test_retriever.py` and
`test_vector_store.py` into exactly one of three dispositions, decided
per-file/per-test rather than assumed:

1. The API surface they exercise is still meant to be supported ->
   update the tests to call the current `add_chunks()`/retriever API for
   real, so they start testing a contract that's actually still true.
2. The API they exercise is legacy and the tests are themselves
   obsolete -> delete them (or replace with real coverage of whatever
   superseded them), rather than keep dead assertions around.
3. The real contract can't be decided correctly until the future
   Hybrid Retrieval/Qdrant replacement lands -> `pytest.mark.xfail(strict=True,
   reason="...")`, so the debt is an explicit, named, tracked xfail
   instead of an ambient "5 failures, don't worry about it" the suite
   silently carries forever.

Your stated preference is (2) or (3) over (1) as a default reflex --
mechanically patching `add_chunks()` call sites to stop the `TypeError`
would make DeepSource go green without confirming either test still
verifies a contract anyone wants preserved, which is worse than an
honest xfail. This audit is scoped narrowly to *classifying* these two
files, not to building whatever replaces them.

## PR #2 review fix, round 2 — validation isolation + real typing bugs

Two of five findings this round were already fixed in `0e93061`
(`_check_output_k`'s `candidate_k`/`output_k` guards, the `sparse_index`
unused-binding nitpick) -- stale review comments from before that commit
landed, no action needed. The other three, verified against current code
before fixing:

**1. `test_candidate_k_zero_or_negative_raises` didn't actually cover
`candidate_k=-1`, and conflated `candidate_k=0` with `output_k=0`
instead of isolating it.** Valid gap: the name promised "zero or
negative" but only tested zero, and pairing it with `output_k=0` (rather
than a valid, positive `output_k`) meant the test didn't cleanly
attribute the raise to `candidate_k` alone. Split into
`test_candidate_k_non_positive_raises`, parametrized over
`candidate_k in (0, -1)` × the three retrievers, always paired with
`output_k=1` (valid) so the failure is unambiguously `candidate_k`'s.

**2. Reviewer also asked to parametrize `output_k` as invalid at both 0
and -1 -- partially disagreed, with a test added to show why.**
`output_k=0` is intentionally *not* rejected: asking for zero results is
a well-defined request (same as Python's `list[:0]`), unlike `output_k=-1`
which is the real footgun (`list[:-1]` silently drops the last element
instead of erroring). Kept `test_output_k_negative_raises` at -1 only,
and added `test_output_k_zero_is_valid` asserting `retrieve_dense(...,
output_k=0) == []` -- makes the design decision an explicit, tested
contract instead of leaving future reviewers to re-raise the same
question against a bare comment.

**3. Two real DeepSource typing findings, both fixed.**
- `src/entities/store.py::_normalize_pair`: declared `-> tuple[str,
  str]` but returned `tuple(sorted((a, b)))`, which mypy only infers as
  `tuple[str, ...]` (the `tuple()` constructor over an arbitrary iterable
  can't be narrowed to a fixed arity). Fixed by unpacking explicitly:
  `a, b = sorted((...)); return a, b`.
- `src/retrieval/version_filter.py::query_version_interval`: called
  `mention_to_interval(mention.normalized, ...)` where `mention.normalized`
  is typed `str | None` (per `VersionMention`'s own field comment: "None
  if the matched text couldn't be normalized") but `mention_to_interval`'s
  first parameter is typed plain `str`. Checked every `VersionMention`
  construction site in `find_version_mentions()` -- all three always set
  `normalized` from a live regex match, so this isn't a reachable runtime
  bug *today*, but the type gap was real and `parse_version_key(None)`
  would crash with `AttributeError` if that ever changed silently. Added
  `or mention.normalized is None` to the existing early-return guard.

**Skipped, with reason**: `PYL-W0105` ("string statement has no effect")
on the triple-quoted string in `tests/test_retrieval_prefix_stability.py`,
placed after the imports. To be precise about what the lint is actually
catching: because it isn't the first statement in the file, it is *not*
the module docstring (doesn't populate `__doc__`) -- it's a plain string
expression Python evaluates and discards, exactly as DeepSource says.
The lint is factually correct, not a false positive. Left unfixed anyway,
because this same placement is used consistently across `retrieval.py`,
`hybrid.py`, `filters.py`, `version_filter.py`, `evaluation.py`, and
others since Stage 6 -- a deliberate, repo-wide convention (context after
imports, not before), not something this one new test file introduced.
Moving just this file's string literal above its imports would make it
inconsistent with every other module in the codebase instead of
consistent with none of them; adopting real module docstrings
repo-wide is a separate, larger style decision, out of scope for this PR.

**Verification**: full suite 174 passed (170 prior + 4 net new: the
`candidate_k` test grew from 3 cases to 6, plus 1 new zero-is-valid
test), same 5 pre-existing unrelated failures. Reran the frozen
benchmark since `version_filter.py` changed: numbers unchanged (Dense
0.964/0.889, BM25 0.810/0.766, Hybrid 0.952/0.875, Hybrid+vf
0.929/0.863), `git diff --stat data/benchmark/ data/gold/` empty --
expected, since the `mention.normalized is None` guard covers a case
that doesn't occur in the current corpus.

**Files modified**: `src/entities/store.py` (`_normalize_pair` typing
fix), `src/retrieval/version_filter.py` (`query_version_interval` `None`
guard), `tests/test_retrieval_prefix_stability.py` (split/parametrize
`candidate_k` test, new `test_output_k_zero_is_valid`).

## Repository health audit — resolve the 5 pre-existing test failures before Stage 8B1

Explicit motivation, stated up front: Stage 8B1 is ranking/reranker
ablation work, where the whole point is noticing a newly-introduced red
test. A `164 passed, 5 known failures` baseline that's been carried
since Stage 4 makes every future failure require manual "is this one of
the five old ones?" triage -- not acceptable heading into a stage whose
job *is* to watch for regressions. Scope, as instructed: only the two
files behind the 5 failures (`tests/test_retriever.py`,
`tests/test_vector_store.py`) and any genuinely high-priority (Bug Risk
/ Typecheck) DeepSource findings surfaced alongside them -- not a
repo-wide cleanup, no style-only findings (`PYL-W0105` and similar left
alone). Branch: `repository-health-audit`, off `main` at `759fe39`
(post-PR-#2 merge).

Each failure classified into exactly one of three outcomes before
touching anything, per your framework: (A) still a real, current
contract -> fix the test to match it; (B) target interface is genuinely
obsolete -> delete the test; (C) contract should exist but isn't
implemented yet -> `xfail(strict=True, reason=...)`. Explicitly avoided
the shortcut of just adding missing arguments to make the `TypeError`
go away without first checking whether the interface being called still
means anything.

**Traced real callers first, not just read the two files in isolation**:
`grep`'d every import of `src.retriever` and `src.vector_store` across
the whole repo (not just the test files). Result: `src/vector_store.py`
is imported by `src/retrieval/dense_index.py` -- genuinely load-bearing,
part of the active Stage 6+ retrieval pipeline. `src/retriever.py` is
imported by **nothing except its own test file** -- every real retrieval
path in this repo goes through `src/retrieval/retrieve_dense/sparse/
hybrid` instead, built from Stage 6 onward as a parallel, independent
stack. `src/retriever.py` was kept back in Stage 1 as "reusable generic
RAG infra"; in practice, only `vector_store.py` from that original set
ended up actually reused -- `retriever.py` never got wired into anything.

**`tests/test_retriever.py` (4 failing tests) -> B, delete the whole
file.** Two independent problems converged here, either one alone would
have been enough:
1. The module under test, `src/retriever.py::retrieve()`, is unused
   dead code in the current architecture (see above) -- fixing tests for
   a function nothing calls doesn't protect anything real.
2. Even setting that aside, the test bodies themselves don't hold up.
   Three of the four (`test_retrieve_top_two_chunks`,
   `test_top_k_greater_than_number_of_chunks`, `test_retrieve_empty_input`)
   call `retrieve(query_embedding, document_embeddings, chunks, top_k)`
   -- a raw-numpy-array signature that does not exist anywhere in current
   `src/` and never has, per the same repo-wide grep. Looks like an early
   draft `retrieve()` design that was abandoned in favor of the
   ChromaDB-collection-based signature `src/retriever.py` actually has,
   with the tests simply never updated or removed at that time. The
   fourth (`test_retrieve_returns_relevant_chunks`) at least calls the
   right *shape* of signature, but its own `add_chunks()` call is missing
   required arguments (so the fixture chunks never actually get indexed),
   and its assertion (`result == ["The office opens at 9 AM."]`) has no
   relationship to the "Solar energy / Wind energy / Cats" input text --
   looks like a copy-paste leftover from an unrelated fixture, not a
   test that was ever passing. `retrieve()` also returns `list[dict]`
   (text/metadata/distance), so this assertion couldn't structurally
   pass even with correct content.

Not xfailed, because xfail says "this contract should exist, just not
yet" -- there is no plan to wire `retriever.py` back into the pipeline;
it's cleanly superseded, not pending. `src/retriever.py` itself removed
after the repository-wide reference check above confirmed zero active
callers -- re-ran the same `rg` search after deleting the test file to
re-verify nothing besides narrative mentions in `README.md`/this log
referenced it before removing the source file too.

**`tests/test_vector_store.py::test_add_chunks` (1 failing test) -> A,
fix to match the current contract.** `add_chunks()` is real and actively
depended on (`dense_index.py`). The test was missing the required
`metadatas` argument and assumed `add_chunks` auto-generates metadata
internally, which it doesn't (the caller is expected to construct it,
same as `dense_index.py`'s `_chunk_metadata()` does). Fixed by
constructing `metadatas=[{"source": "sample.pdf"}, {"source": "sample.pdf"}]`
explicitly and passing it through -- kept, not replaced, because this is
the *only* test anywhere in the suite covering `add_chunks`'s
`ids=None` default-id-derivation branch (`test_dense_index.py` only
exercises the explicit-`ids` path), genuinely non-redundant coverage.

**DeepSource Bug Risk / Typecheck check**: no fresh findings were
available to triage in this session (no live DeepSource dashboard
access, no pasted output for this round) -- noted rather than skipped
silently. If real Bug Risk/Typecheck findings turn up on this branch's
PR, they'll get the same verify-against-current-code treatment as the
`PYL-E1120`/`TYP-005`/`TYP-050` findings earlier in this log; style-only
findings (`PYL-W0105` and similar) are out of scope per your instruction.

**Result**: 175 passed, 0 failed, 0 xfailed -- not the 179 you sketched
as an illustrative target, and deliberately so: that number assumed all
5 would resolve via (A); 4 resolved via (B) instead, so the honest count
is smaller but every one of the 175 is a real, currently-meaningful test.
Full suite confirmed clean; no retrieval algorithm, chunking, Gold Set
v1, or benchmark code touched.

**Files removed**: `tests/test_retriever.py`, `src/retriever.py`.

**Files modified**: `tests/test_vector_store.py` (`test_add_chunks`
fixed to pass `metadatas`).

## Stage 8B1 — Ranking ablation: weighted RRF + Qwen3-Reranker-0.6B

Branch: `stage8b1-ranking-ablation`, off `main` at `ceeb052`
(post-repository-health-audit merge, 175 passed baseline). Scope, as
instructed: controlled ranking experiments only -- RRF 1:1 / Dense:BM25
2:1 / Dense:BM25 1:2 / post-fusion reranking with Qwen3-Reranker-0.6B.
Explicitly unchanged: Gold Set v1, MiniLM (`all-MiniLM-L6-v2`), chunking,
corpus, `candidate_k=40` (Stage 8B0's protocol), query rewriting (still
none), version-filter semantics.

**Weighted RRF** (`src/retrieval/hybrid.py`, `src/retrieval/retrieval.py`):
`reciprocal_rank_fusion()` gained an optional `weights` param -- each
ranking's score contribution is `weight / (k + rank)` instead of a fixed
`1 / (k + rank)`. `weights=None` (the default, and every pre-8B1 caller)
reproduces the original unweighted formula exactly -- verified by a
regression test asserting `weights=None` and `weights=[1.0, 1.0]`
produce identical output, plus rerunning `run_pydantic_benchmark.py`
afterward and confirming its CSVs stayed byte-identical.
`retrieve_hybrid()` threads an optional `weights: tuple[float, float]`
(dense, sparse) through to fusion, same backward-compatible default.
Added `test_extreme_dense_weight_converges_on_dense_only_ranking`: a
corpus-independent, mathematically-guaranteed wiring test (as one
weight dominates the other, RRF's fused order must converge on the
dominant ranking's own order, since ranks are a tie-free permutation) --
proves `weights=` actually reaches fusion, not just "looks plausible."

**Reranker** (`src/retrieval/reranker.py`): wraps `Qwen/Qwen3-Reranker-0.6B`
via `sentence_transformers.CrossEncoder`, lazily loaded as a module-level
singleton (~1.2GB, downloaded once and cached locally; smoke-tested
directly before building anything around it -- a relevant pair scored
10.25, an irrelevant pair -10.56, cleanly separated). `rerank(query_text,
candidates, output_k, model=None)` scores every candidate against the
query, sorts, slices to `output_k`, and rebuilds `RetrievedChunk` objects
with updated `score`/`rank`. `model` is injectable specifically so
`tests/test_reranker.py` (5 tests) can exercise the sort/slice/rebuild
logic against a stub `.predict()` implementation instead of loading the
real 1.2GB model on every default `pytest` run -- the real model's
actual reranking quality is validated by the ablation script against
real data instead, not the fast unit suite. Deliberately not folded into
`retrieve_hybrid()` itself: reranking is an explicit opt-in
post-processing step over whatever candidate pool the caller already
has, same separation of concerns as `filters.apply_filters`.

**`scripts/run_ranking_ablation.py`** (new, does not modify
`run_pydantic_benchmark.py`): imports `load_gold`/`build_resolvers`/
`aggregate`/`write_csv` from the frozen benchmark runner rather than
reimplementing them, so there's no way for this script's corpus/gold/
scoring conventions to silently drift from the frozen baseline's. Four
modes: `rrf_1_1` (baseline, reproduced here for side-by-side display,
not a second frozen artifact), `rrf_dense2_sparse1`,
`rrf_dense1_sparse2`, and `hybrid_reranked` (retrieves the *unweighted*
RRF 1:1 candidate_k=40 pool in full, i.e. `output_k=CANDIDATE_K`, then
reranks that whole pool and slices to `OUTPUT_K=10` -- reranking scores
on top of the standard fusion's own pool, not a separately-pooled
candidate set). Scored over the same 42-query `change_retrieval` core as
the frozen benchmark, plus a focused rank trace for `q_nl_02`/`q_nl_03`
specifically (the two known Stage 8A/8A.2 failures this ablation exists
to investigate).

**Results** (42-query `change_retrieval` core, change-level):

| Mode | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|
| `rrf_1_1` (= frozen `hybrid`) | 0.952 | 0.875 | 0.895 |
| `rrf_dense2_sparse1` | 0.952 | 0.887 | 0.902 |
| `rrf_dense1_sparse2` | 0.905 | 0.889 | 0.893 |
| `hybrid_reranked` | **0.976** | **0.964** | **0.967** |

`rrf_1_1` matches the frozen `hybrid` baseline exactly (0.952/0.875),
confirming the weighted-fusion machinery doesn't perturb the unweighted
path. Weighting toward Dense (2:1) improves MRR/nDCG without hurting
Recall@5; weighting toward Sparse (1:2) trades Recall@5 down (0.952 ->
0.905) for a marginally better MRR -- a real, reportable tradeoff, not
noise. Reranking is the clear winner across every metric: Recall@5
0.952 -> 0.976, MRR 0.875 -> 0.964, a meaningfully better ranking of the
same underlying RRF 1:1 candidate pool.

**Focus queries**:

- **`q_nl_03`** ("How do I validate a plain dict into a model object
  now?") -- **fixed by reranking**: `NOT FOUND in top 10` under all
  three RRF variants, rank **2** (Recall@5=1.0) under `hybrid_reranked`.
  This is exactly the Stage 8A.2 hypothesis validated: Dense finds the
  right chunk on its own (top-5), plain RRF fusion buries it (rank
  ~11/40 per Stage 8A.2's diagnosis), and reranking *over the fused
  pool* recovers it -- a fusion-dilution problem, not a ranking-model
  problem, solved exactly the way it was predicted to be solvable.
- **`q_nl_02`** ("What's the new way to build a model instance while
  skipping validation?") -- **not fixed by any mode tested**, reranking
  included. Worth stating precisely what this does and doesn't show:
  this ablation's rank trace only reports whether the target lands in
  each mode's final `output_k=10`, not whether it's present deeper in
  the underlying `candidate_k=40` pool that `hybrid_reranked` reranks
  over -- if the target never entered that fused 40-item pool to begin
  with, no reranker operating strictly within it could ever surface it,
  a different failure mode than "ranked too low within the pool." That
  distinction needs a `diagnose_failed_queries.py`-style deeper trace to
  resolve, not asserted here from the ablation's headline numbers alone.

**Verification**: full suite 185 passed (175 prior + 10 new: 3
`test_hybrid.py` weight tests, 2 `test_retrieval_integration.py` weight
tests, 5 `test_reranker.py` stub-model tests), no pre-existing failures.
Frozen `run_pydantic_benchmark.py` rerun after all changes: numbers and
CSVs byte-identical to the Stage 8B0 baseline (Dense 0.964/0.889, BM25
0.810/0.766, Hybrid 0.952/0.875, Hybrid+vf 0.929/0.863). Gold Set v1
regenerated through the guarded generator: digest matched, `git diff`
on `data/gold/` empty. `pydantic-gold-v1` tag untouched.

**Files added**: `src/retrieval/reranker.py`,
`scripts/run_ranking_ablation.py`, `tests/test_reranker.py`,
`data/benchmark/ranking_ablation_aggregate_results.csv`,
`data/benchmark/ranking_ablation_per_query_results.csv`.

**Files modified**: `src/retrieval/hybrid.py` (weighted
`reciprocal_rank_fusion`), `src/retrieval/retrieval.py`
(`retrieve_hybrid` `weights` param), `tests/test_hybrid.py`,
`tests/test_retrieval_integration.py` (weighted-fusion tests, plus an
unrelated `next()`-without-default hygiene fix flagged during this
stage -- see below), `scripts/generate_pydantic_gold_set.py`,
`src/extraction/change_extraction.py` (unrelated typing/invariant fixes,
see below).

**Unrelated fixes folded in during this stage** (verified against
current code, kept minimal, don't touch retrieval/ranking logic):
- `tests/test_retrieval_integration.py`: a bare `next(... )` with no
  default would raise an opaque `StopIteration` if the expected test
  chunk were ever missing from the fixture corpus. Now raises a clear
  `assert ... is not None, "Expected ... chunk in test corpus"` instead.
- `src/extraction/change_extraction.py::_find_external_refs`: same bare
  `next()` pattern over regex capture groups. Verified the underlying
  invariant actually holds (`_EXTERNAL_REF_RE` is a top-level alternation
  with exactly one capturing group per branch, each requiring `\d+`, so
  a successful match structurally guarantees exactly one non-`None`
  group) -- not a provable-by-static-analysis fact, so made it an
  explicit `raise ValueError(...)` instead of an implicit `StopIteration`
  if it were ever violated by a future regex edit.
- `scripts/generate_pydantic_gold_set.py`: `by_type`/`by_scope` summary
  dicts indexed with `q["query_type"]`/`q["evaluation_scope"]`, which
  mypy widened to `Sequence[str]` (not `str`) because the same dict
  literal also holds `list[str]`-valued keys (`required_change_ids`
  etc.), and `str` and `list[str]`'s common supertype is `Sequence[str]`.
  Not a runtime bug (those two keys are always real strings), but a real
  type-inference gap. Fixed by wrapping with `str(...)` at the two
  print-summary call sites -- minimal, doesn't restructure `gold`'s
  broader untyped-dict shape (a `TypedDict` would be the "proper" fix,
  out of scope for a two-line DeepSource finding). Verified via
  regeneration: frozen guard passed, `git diff` on `data/gold/` empty.

## Stage 8B1 wrap-up — q_nl_02 deep dive + reranker latency/reproducibility

Two follow-ups requested before opening the Stage 8B1 PR, both
investigation-only -- no retrieval/ranking code changed.

### `q_nl_02` deep dive: exactly where does it fail?

The ablation's headline table only reports "found in final `output_k=10`
or not" -- not precise enough to say *why* `hybrid_reranked` still
misses it. Traced the single required chunk
(`chunk_a93f778ef1d8b5aa`, "`BaseModel.construct()` was replaced by
`BaseModel.model_construct()` in v2.0.0.") through every stage for the
query "What's the new way to build a model instance while skipping
validation?":

| Stage | Target's rank |
|---|---|
| Dense-only `candidate_k=40` pool | 20 |
| Sparse-only `candidate_k=40` pool | not found |
| RRF 1:1 fused `candidate_k=40` pool | **34** |
| After reranking that same 40-item pool | **11** |

So it's not any single one of the three hypothesized failure modes
cleanly -- it's a *sequence*: Dense alone ranks it a middling 20/40;
fusion with Sparse (which never finds it at all) actively **hurts** it,
dropping it to 34/40 -- the same dilution mechanism `q_nl_03` suffered
from, confirmed here as not unique to that query. Reranking then
recovers most of that lost ground, 34 -> 11, but lands **one rank short**
of `output_k=10`. Not "reranker doesn't help" -- reranker cut the gap by
23 positions and still wasn't quite enough. Distinguishes cleanly from
`q_nl_03` (which fusion also dilutes, but reranking clears the bar
completely, landing at rank 2): same failure mechanism, different
distance from the finish line, which is exactly why one query resolved
and the other didn't even though both look like "RANKING" failures on
the surface.

### Reranker latency and reproducibility

**Reproducibility**: model `Qwen/Qwen3-Reranker-0.6B`, revision
`e61197ed45024b0ed8a2d74b80b4d909f1255473` (HF Hub commit sha, pinned
here for the record -- `reranker.py` itself loads by model name, not a
pinned revision, so a future re-run could pick up a newer upload unless
this is checked); `sentence-transformers` 5.6.1, `transformers` 5.14.1,
`torch` 2.13.0+cpu; device `cpu` (no CUDA available in this
environment); `CrossEncoder.predict`'s default `batch_size=32` (never
overridden by `reranker.py`); `candidate_k=40` (Stage 8B0's fixed pool,
unchanged); model `max_length=40960`.

**Latency**: first measurement attempt was invalid and is recorded here
only as a methodology note, not a result -- it used `time.perf_counter()`
(wall clock) around a long unattended background run, and the session's
own date rolled over mid-run, confirming the measurement window
included a real system sleep/suspend that wall-clock timing can't
distinguish from actual compute (`37271s` total, `887s` average, one
query showing `29653s` -- physically impossible for this workload).
Re-measured with `time.process_time()` (CPU time, which cannot advance
while a process isn't scheduled, so it's immune to suspend) as well as
a fresh wall-clock pass. CPU time came back *larger* than wall time
(42007s vs 10088s total, ratio ~4.16) -- not a bug: `process_time()`
sums CPU time across every thread, and this machine's torch/BLAS
backend is evidently using ~4 threads per forward pass, so CPU time
measures aggregate compute cost, not what a caller actually waits for.
The wall-clock component of this second, uninterrupted run is what's
reported as latency, cross-checked against the first (corrupted) run's
minimum value -- 82.3s vs 79.6s, close enough to confirm the first run's
extreme values were the suspend artifact, not this run's numbers:

| Metric | Value |
|---|---|
| Model load (cold, from local HF cache) | 2.87s |
| Rerank wall time per query (mean, 42 queries, up to 40 candidates each) | 240.2s |
| Rerank wall time per query (min / max) | 82.3s / 324.7s |
| Rerank wall time, all 42 queries | ~10,088s (~2.8 hours) |

**Honest read**: ~4 minutes per query on CPU is not remotely
production-viable as deployed here -- this is a research-ablation
result establishing that reranking *can* improve ranking quality
(confirmed above), not a claim that this specific model/hardware
combination is deployable. A real deployment would need GPU inference,
a smaller/distilled reranker, or both; recorded here as an explicit,
quantified limitation rather than left implicit.

**Files modified**: none (investigation-only; both scripts used for
this section were run from a local scratch location, not checked into
the repo, since they're one-off diagnostics over already-existing
`retrieve_hybrid`/`rerank` APIs, not new reusable tooling).
