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
