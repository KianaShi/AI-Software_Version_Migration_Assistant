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

The current implementation focuses on the entity-resolution and evidence-aggregation layer.

Level 1 extraction and the final retrieval pipeline are planned next.

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

Level 1 extraction is the next major implementation stage.

---

# Testing

The entity and aggregation modules currently include **35 passing tests** covering:

* entity models
* candidate blocking
* hard cannot-link constraints
* change-type compatibility
* pairwise scoring
* signal-level score inspection
* ambiguous candidate handling
* precision-first linking behavior
* SQLite entity persistence
* confidence presentation

Several tests intentionally focus on difficult negative cases where evidence shares a symbol or similar language but should **not** be merged.

There are also five pre-existing failures in legacy retriever/vector-store tests caused by historical interface mismatches.

Those failures existed before the entity/aggregation work and are intentionally being kept outside the scope of the current implementation.

The legacy retrieval layer will be revisited when the new retrieval architecture is introduced.

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

Planned retrieval work includes:

* source-aware document parsing
* version metadata
* Late Chunking experiments for documentation
* Tree-sitter parsing for source code
* dense + sparse hybrid retrieval
* reranking
* version-aware filtering
* multi-hop migration queries
* adaptive evidence retrieval

These components are part of the roadmap and are **not yet represented as completed features**.

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

Planned metrics:

* Recall@K
* MRR
* nDCG
* Migration Chain Recall
* affected-symbol coverage

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

### In Progress / Next

* [ ] Level 1 source ingestion
* [ ] Change extraction
* [ ] Symbol normalization
* [ ] Version normalization
* [ ] Extraction provenance and confidence
* [ ] Human-verified linkage evaluation set

### Planned

* [ ] Source-aware chunking
* [ ] Late Chunking benchmark
* [ ] Tree-sitter code parsing
* [ ] Hybrid dense + sparse retrieval
* [ ] Reranking
* [ ] Version-aware RAG
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
