# Shakespeare RAG

> 🚧 **Work in Progress**\
> A benchmark-driven Retrieval-Augmented Generation (RAG) project for
> Shakespeare that explores structure-aware retrieval, evaluation, and
> an agentic retrieval workflow.

------------------------------------------------------------------------

## ✨ Overview

This project builds a RAG system from scratch rather than relying on
high-level frameworks. It focuses on understanding and improving each
stage of the retrieval pipeline using Shakespeare's plays as a
structured knowledge base.

Current goals:

-   Build a transparent RAG pipeline
-   Preserve play, act, scene, and speaker metadata
-   Evaluate retrieval quality using an external benchmark
-   Improve retrieval through reranking
-   Extend the system with an agentic retrieval workflow

------------------------------------------------------------------------

## 🧠 Current Pipeline

``` text
MIT Shakespeare HTML
        ↓
HTML Parser
        ↓
Speech Records + Metadata
        ↓
Context-Aware Dialogue Chunking
        ↓
Embeddings
        ↓
ChromaDB
        ↓
Dense Retrieval
        ↓
Top-K Evidence
        ↓
Prompt Builder
        ↓
LLM (planned)
```

------------------------------------------------------------------------

## 🚀 Current Features

### Completed

-   ✅ TXT and PDF document loaders
-   ✅ MIT Shakespeare HTML parser
-   ✅ Structured metadata extraction
-   ✅ Context-aware dialogue chunking
-   ✅ ChromaDB vector store
-   ✅ Dense semantic retrieval
-   ✅ Prompt builder
-   ✅ Hamlet corpus indexing
-   ✅ Benchmark loader (507 QA records)
-   ✅ Unit tests with pytest

### In Progress

-   ⏳ Retrieval evaluation (Recall@K / MRR)
-   ⏳ Cross-Encoder reranking
-   ⏳ LLM answer generation
-   ⏳ Interactive web interface

------------------------------------------------------------------------

## 📊 Evaluation

The retriever will be evaluated using an external Shakespeare benchmark.

Planned metrics:

-   Recall@1
-   Recall@3
-   Recall@5
-   Mean Reciprocal Rank (MRR)
-   Retrieval latency

The benchmark is used **only for evaluation** and is never inserted into
the vector database.

------------------------------------------------------------------------

## 🤖 Planned Agentic Retrieval Workflow

Instead of treating retrieval as a single step, the future system will
iteratively improve evidence quality before generating an answer.

``` text
User Question
      ↓
Query Planner
      ↓
Dense Retrieval
      ↓
Cross-Encoder Reranker
      ↓
Evidence Controller
   ┌───────────────┴───────────────┐
Evidence sufficient      Evidence insufficient
        ↓                         ↓
Answer Validator     Query Rewrite & Retry
        ↓
Final Answer + Citations
```

### Query Planner

-   Detect simple vs. comparative questions
-   Decompose complex queries
-   Apply metadata filters

### Evidence Controller

-   Perform dense retrieval
-   Apply reranking
-   Evaluate evidence sufficiency
-   Retry retrieval with rewritten queries

### Answer Validator

-   Generate answers from retrieved evidence
-   Attach play, act, and scene citations
-   Detect unsupported claims

------------------------------------------------------------------------

## 🛠️ Tech Stack

-   Python
-   Beautiful Soup
-   Sentence Transformers
-   ChromaDB
-   NumPy
-   Pytest
-   OpenAI API *(planned)*
-   LangGraph *(planned)*

------------------------------------------------------------------------

## 🗺️ Roadmap

### Core RAG

-   [x] Parsing
-   [x] Chunking
-   [x] Dense Retrieval
-   [x] Benchmark Loader
-   [ ] Retrieval Evaluation
-   [ ] Cross-Encoder Reranking
-   [ ] LLM Integration

### Agentic Workflow

-   [ ] Query Planner
-   [ ] Evidence Controller
-   [ ] Query Rewrite & Retry
-   [ ] Answer Validator
-   [ ] Citation Validation

### Application

-   [ ] Web UI
-   [ ] Interactive Shakespeare QA
-   [ ] Retrieval Visualization

------------------------------------------------------------------------

## 🎯 Goal

Build an explainable Shakespeare RAG system that not only retrieves
relevant passages, but also measures retrieval quality, validates
evidence, and progressively evolves into an agentic retrieval system.
