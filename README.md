# Shakespeare RAG

> 🚧 **Work in Progress**  
> A structure-aware Shakespeare question-answering system with benchmark-driven retrieval evaluation and planned multi-agent failure recovery.

---

## ✨ Overview

Shakespeare's works are long, highly structured, and distributed across plays, acts, scenes, speakers, and speeches. This project explores how Retrieval-Augmented Generation (RAG) can answer questions about Shakespeare while grounding responses in the original text.

Rather than relying entirely on a high-level RAG framework, the core pipeline is implemented step by step in Python. This makes each stage easier to inspect, test, and improve:

- document loading
- HTML parsing
- chunking
- embedding generation
- vector storage
- retrieval
- prompt construction
- evaluation
- answer generation

The project began as a general RAG learning pipeline using TXT and PDF documents. It was later extended into a Shakespeare-focused system because plays provide meaningful literary structure—work, act, scene, speaker, and dialogue—that can be preserved and tested during retrieval.

The current implementation can parse and index Hamlet scene files, preserve structured metadata, build a persistent ChromaDB vector store, and retrieve relevant dialogue for natural-language questions.

---

## 🧠 Current System Pipeline

```text
MIT Shakespeare HTML Files
            ↓
Scene-Level HTML Parsing
            ↓
Speech Records + Metadata
            ↓
Context-Aware Dialogue Chunking
            ↓
Sentence-Transformer Embeddings
            ↓
Persistent ChromaDB Collection
            ↓
Question Embedding
            ↓
Dense Vector Retrieval
            ↓
Top-K Evidence Chunks
            ↓
Prompt Construction
            ↓
LLM Answer Generation (next stage)
```

The planned agentic workflow will later add evidence checking, query rewriting, retries, critique, citation validation, and execution tracing.

```text
User Question
      ↓
Planner Agent
      ↓
Retrieval Agent
      ↓
Evidence Agent
   ┌──┴──────────────┐
Evidence sufficient  Evidence insufficient
   ↓                  ↓
Answer Agent      Rewrite Query
   ↓                  ↓
Critic Agent      Retry Retrieval
   ↓
Final Answer + Sources + Trace
```

---

## 🚀 Current Features

- ✅ TXT document loader
- ✅ PDF document loader
- ✅ General fixed-size text chunker
- ✅ Embedding generation with `all-MiniLM-L6-v2`
- ✅ Query embedding generation
- ✅ Dense semantic retrieval
- ✅ Persistent ChromaDB storage
- ✅ Metadata-aware vector records
- ✅ Prompt builder
- ✅ MIT Shakespeare scene-level HTML parser
- ✅ Structured extraction of:
  - work
  - act
  - scene
  - speaker
  - speech
- ✅ Context-aware dialogue window chunking
- ✅ Corpus ingestion script
- ✅ Automatic filtering of non-scene HTML files
- ✅ Collection reset and reproducible rebuilding
- ✅ Retrieval demo with Top-K results, metadata, and distances
- ✅ Hamlet index containing 20 scene files and 986 speech-centered chunks
- ✅ Automated benchmark loading from multiple JSON files
- ✅ Five-play benchmark subset with 507 question-answer records
- ✅ Unit tests with pytest
- ⏳ Cross-Encoder reranking
- ⏳ Retrieval evaluation
- ⏳ LLM response generation
- ⏳ Multi-agent planning and evidence verification
- ⏳ Query rewriting and retry logic
- ⏳ Citation validation
- ⏳ Interactive Shakespeare Q&A interface

---

## 📚 Data Sources

### Shakespeare Corpus

The project uses HTML editions from the MIT Shakespeare corpus as the retrieval knowledge base.

- **Source:** TheMITTech/shakespeare
- **Repository:** `https://github.com/TheMITTech/shakespeare`
- **Usage:** Parsing, metadata extraction, chunking, embedding generation, and retrieval

The source repository contains both scene-level files and non-scene files such as `full.html`, `index.html`, or play-level overview files. The ingestion pipeline intentionally indexes only files matching the scene pattern:

```text
work.act.scene.html
```

Example:

```text
hamlet/hamlet.3.1.html
```

Non-scene source files are preserved but skipped during indexing to avoid duplicate content and invalid act/scene metadata.

Parsed speech record:

```python
{
    "work": "hamlet",
    "act": 3,
    "scene": 1,
    "speaker": "HAMLET",
    "speech": "To be, or not to be..."
}
```

The current local knowledge base contains Hamlet. Additional plays will be added after retrieval behavior is evaluated on the initial corpus.

### Evaluation Benchmark

Retrieval and answer-generation performance will be evaluated using selected files from:

- **Dataset:** Hananguyen12/QA-shakespeare-plays-dataset
- **Platform:** Hugging Face
- **Source:** `https://huggingface.co/datasets/Hananguyen12/QA-shakespeare-plays-dataset/tree/main`
- **License:** MIT

The current evaluation subset contains **507 questions across five plays**:

- Hamlet
- Macbeth
- Othello
- King Lear
- Romeo and Juliet

Example benchmark record:

```python
{
    "id": "hamlet_001",
    "play": "The Tragedy of Hamlet, Prince of Denmark",
    "category": "factual",
    "difficulty": "basic",
    "question": "...",
    "answer": "...",
    "act": "1",
    "scene": "5",
    "characters": ["Hamlet", "Ghost", "Claudius"],
    "themes": ["revenge", "supernatural"]
}
```

Benchmark files are used **only for evaluation** and are not inserted into the vector database. This separation helps prevent benchmark leakage.

---

## 📖 Knowledge Base Design

The corpus preserves literary structure wherever possible:

```text
Work
 └── Act
      └── Scene
           ├── Stage Direction
           └── Speech
                ├── Speaker
                └── Dialogue
```

The Shakespeare loader converts each valid scene file into structured speech records.

```python
{
    "work": "hamlet",
    "act": 3,
    "scene": 1,
    "speaker": "OPHELIA",
    "speech": "O, help him, you sweet heavens!"
}
```

This metadata supports:

- play-level filtering
- act and scene filtering
- character-specific retrieval
- source attribution
- benchmark evaluation
- future citation validation

Stage directions are excluded when they appear as separate non-speech blocks. Stage directions embedded inside a spoken block may remain part of the dialogue text.

---

## 🔬 Chunking Evolution

Chunking was treated as an experimental design decision rather than a fixed preprocessing step.

### Baseline: Fixed-Size Chunking

The original general-purpose chunker combines a configurable number of text lines.

```text
Document Lines
      ↓
Fixed-Size Groups
      ↓
Text Chunks
```

This strategy remains useful for TXT, PDF, and other documents that do not have clear semantic boundaries.

### Version 1: One Speech per Chunk

The first Shakespeare-specific implementation treated each speech as one semantic chunk.

```text
One Speech
    ↓
One Chunk
```

This preserved speaker metadata cleanly, but retrieval testing exposed a weakness: important events may be distributed across adjacent speakers.

For the question:

```text
Who killed Polonius?
```

the retriever often returned lines containing the name `Polonius`, while the crucial killing evidence appeared in nearby dialogue that did not explicitly mention his name.

### Version 2: Context-Aware Dialogue Window

The current strategy uses each speech as the center of a small dialogue window:

```text
Previous Speech
       +
Current Speech
       +
Next Speech
       ↓
Contextual Chunk
```

The metadata continues to describe the center speech, while the chunk text preserves local conversational context.

This approach:

- preserves dialogue flow
- captures interactions between speakers
- avoids arbitrary character boundaries
- keeps chunks within the same scene file
- improves candidate retrieval for event-based questions
- provides better evidence for future reranking and answer generation

The current experiment shows that dialogue windows improve context coverage, although dense retrieval can still prefer lexical matches. A Cross-Encoder reranker is planned to improve final ranking.

---

## 🔎 Retrieval Behavior

The retriever performs the following steps:

```text
User Question
      ↓
Question Embedding
      ↓
ChromaDB Similarity Search
      ↓
Top-K Chunks
      ↓
Text + Metadata + Distance
```

Example usage:

```python
results = retrieve(
    collection=collection,
    question="Who killed Polonius?",
    top_k=5,
)
```

Each result contains:

```python
{
    "text": "...",
    "metadata": {
        "work": "hamlet",
        "act": 3,
        "scene": 4,
        "speaker": "HAMLET"
    },
    "distance": 0.82
}
```

Smaller ChromaDB distance values indicate greater vector similarity under the collection's configured distance behavior.

---

## 🧪 Running the Project

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add the Shakespeare corpus

Place scene-level HTML files under:

```text
data/
└── corpus/
    └── shakespeare/
        └── hamlet/
            ├── full.html
            ├── hamlet.1.1.html
            ├── hamlet.1.2.html
            └── ...
```

The source-level `full.html` file may remain in the folder. The ingestion script automatically skips files that do not follow the `work.act.scene.html` naming pattern.

### 3. Build the vector store

Run commands from the project root:

```bash
py -m scripts.build_vector_store
```

The script:

1. recursively discovers HTML files
2. skips non-scene files
3. parses structured speeches
4. creates contextual dialogue chunks
5. generates embeddings
6. stores chunks and metadata in ChromaDB

Current Hamlet build result:

```text
Processed files: 20
Stored speeches: 986
Collection count: 986
```

### 4. Run the retrieval demo

```bash
py -m scripts.demo_retrieval
```

The demo prints:

- the input question
- Top-K retrieved chunks
- work, act, scene, and speaker metadata
- vector distance values

### 5. Run tests

```bash
py -m pytest -v
```

Tests cover the main RAG components, including loaders, chunking, embeddings, retrieval, prompt construction, benchmark loading, Shakespeare parsing, and vector storage.

---

## 📊 Evaluation Plan

The project uses an external Shakespeare QA benchmark rather than relying only on manually selected demo questions.

### Planned Retrieval Metrics

- Recall@1
- Recall@3
- Recall@5
- Mean Reciprocal Rank
- Retrieval latency
- Correct play rate
- Correct act and scene rate

Example:

```text
Question:
Who says “To be, or not to be,” and in what context?

Expected source:
Hamlet — Act 3, Scene 1
```

The retriever succeeds when the expected scene appears within the returned Top-K results.

### Planned Answer Metrics

- Exact Match for short factual answers
- Token-level F1
- ROUGE-L
- Semantic similarity
- LLM-based answer grading
- Citation support rate
- Unsupported claim rate

### Breakdown Analysis

Results can be analyzed by category:

```text
Category
├── factual
├── interpretive
├── quote
└── scene
```

and difficulty:

```text
Difficulty
├── basic
├── intermediate
└── advanced
```

This makes it possible to identify specific failure patterns rather than reporting only one overall score.

---

## 🤖 Planned Multi-Agent Failure Recovery

The future system is planned as a failure-aware multi-agent workflow.

### Planned Agents

**Planner Agent**

- identifies the question type
- selects relevant plays or characters
- breaks complex comparisons into subqueries

**Retrieval Agent**

- searches the Shakespeare knowledge base
- applies metadata filters
- adjusts Top-K
- rewrites weak queries

**Evidence Agent**

- evaluates whether retrieved passages support the question
- checks play, act, scene, and character coverage
- detects missing evidence

**Answer Agent**

- generates an answer using only validated evidence
- attaches play, act, and scene citations

**Critic Agent**

- checks unsupported claims
- validates citations
- requests revision when evidence is insufficient

### Planned Failure Cases

The system will explicitly handle:

- low-relevance retrieval
- incorrect play retrieval
- incomplete multi-play coverage
- missing character evidence
- unsupported answer claims
- invalid citations
- tool failures
- repeated failed retries
- low-confidence outputs

Possible recovery actions include:

```text
Query Rewrite
Metadata Filter
Higher Top-K
Cross-Encoder Reranking
Fallback Search
Answer Revision
Human Review
Graceful Failure
```

Execution traces will record agent decisions, retries, failures, and final outcomes.

---

## 🛠️ Tech Stack

- Python
- Beautiful Soup
- PyPDF
- Pytest
- NumPy
- Sentence Transformers
- ChromaDB
- OpenAI API *(planned)*
- LangGraph *(planned for agent workflow)*

---

## 📂 Project Structure

```text
rag-chatbot/
│
├── benchmark/
│   ├── Hamlet.json
│   ├── King_Lear.json
│   ├── Othello.json
│   ├── macbeth.json
│   └── romeo_juliet.json
│
├── chroma_db/
│
├── data/
│   ├── corpus/
│   │   └── shakespeare/
│   │       └── hamlet/
│   │           ├── full.html
│   │           ├── hamlet.1.1.html
│   │           └── ...
│   ├── sample.pdf
│   └── sample.txt
│
├── docs/
│   ├── architecture-day1.png
│   └── notes.md
│
├── scripts/
│   ├── __init__.py
│   ├── build_vector_store.py
│   └── demo_retrieval.py
│
├── src/
│   ├── __init__.py
│   ├── benchmark_loader.py
│   ├── document_loader.py
│   ├── shakespeare_loader.py
│   ├── chunker.py
│   ├── embedding.py
│   ├── retriever.py
│   ├── vector_store.py
│   └── prompt_builder.py
│
├── tests/
│   ├── test_benchmark_loader.py
│   ├── test_chunker.py
│   ├── test_embedding.py
│   ├── test_loader.py
│   ├── test_prompt_builder.py
│   ├── test_retriever.py
│   ├── test_shakespeare_loader.py
│   └── test_vector_store.py
│
├── .gitignore
├── README.md
└── requirements.txt
```

Planned additions:

```text
src/
├── reranker.py
├── llm.py
├── pipeline.py
│
├── agents/
│   ├── planner.py
│   ├── retrieval_agent.py
│   ├── evidence_agent.py
│   ├── answer_agent.py
│   └── critic_agent.py
│
├── runtime/
│   ├── state.py
│   ├── workflow.py
│   ├── retry_policy.py
│   └── trace.py
│
└── evaluation/
    ├── retrieval_evaluator.py
    ├── answer_evaluator.py
    └── report.py
```

---

## 🗺️ Roadmap

### Core RAG Pipeline

- [x] TXT document loader
- [x] PDF document loader
- [x] Fixed-size text chunker
- [x] Embedding generation
- [x] Question embedding generation
- [x] Dense semantic retriever
- [x] Persistent ChromaDB storage
- [x] Prompt builder
- [x] Retrieval demo
- [ ] Cross-Encoder reranker
- [ ] LLM integration
- [ ] End-to-end answer pipeline

### Shakespeare Knowledge Base

- [x] Inspect MIT Shakespeare HTML structure
- [x] Parse work, act, and scene metadata
- [x] Extract speaker and speech records
- [x] Exclude separate stage-direction blocks
- [x] Add Shakespeare loader tests
- [x] Import Hamlet scene files
- [x] Store structured metadata in ChromaDB
- [x] Implement context-aware dialogue chunking
- [x] Build the Hamlet vector index
- [ ] Add automated corpus download/setup script
- [ ] Import additional Shakespeare plays
- [ ] Build the full multi-play vector index
- [ ] Evaluate alternative dialogue window sizes

### Evaluation

- [x] Select five benchmark plays
- [x] Add 507 benchmark QA records
- [x] Implement automated benchmark loader
- [x] Add benchmark loader tests
- [ ] Measure Recall@1, Recall@3, and Recall@5
- [ ] Measure Mean Reciprocal Rank
- [ ] Measure retrieval latency
- [ ] Compare single-speech and dialogue-window chunking
- [ ] Compare dense retrieval with reranked retrieval
- [ ] Evaluate results by category and difficulty
- [ ] Add answer-quality evaluation
- [ ] Generate evaluation reports

### Agentic Workflow

- [ ] Wrap retrieval as a Shakespeare search tool
- [ ] Implement shared agent state
- [ ] Add Planner Agent
- [ ] Add Retrieval Agent
- [ ] Add Evidence Agent
- [ ] Add Answer Agent
- [ ] Add Critic Agent
- [ ] Add query rewriting and retry logic
- [ ] Add citation validation
- [ ] Add execution tracing
- [ ] Add failure-rate and retry-rate evaluation
- [ ] Add human-review routing for unresolved cases

### Application

- [ ] Interactive Shakespeare Q&A interface
- [ ] Display cited play, act, scene, and speaker metadata
- [ ] Display agent execution trace
- [ ] Display retrieval and evaluation statistics

---

## 🎯 Goal

The goal of this project is not only to create a working Shakespeare chatbot, but also to build and evaluate a transparent retrieval system that can detect and recover from failure.

The project explores:

- how dialogue-aware chunking affects retrieval quality
- how literary structure and metadata affect retrieval
- how retrieval quality can be measured
- how benchmark leakage can be prevented
- how dense retrieval can be improved with reranking
- how evidence can be validated before answer generation
- how multi-agent systems can recover from weak retrieval
- how execution traces can make agent behavior observable
- how retrieval and answer quality vary across question types and difficulty levels

The final system will provide a searchable Shakespeare research experience backed by original texts, structured citations, benchmark evaluation, and failure-aware agent execution.

---

## 📌 Status

> 🚧 **This project is actively under development.**

Current progress includes:

- a general RAG foundation
- TXT and PDF document support
- a scene-level MIT Shakespeare HTML parser
- structured speech metadata extraction
- context-aware dialogue chunking
- persistent ChromaDB indexing
- a 986-chunk Hamlet knowledge base built from 20 scene files
- dense retrieval with metadata and distance inspection
- an automated benchmark loader
- a 507-question benchmark subset across five plays
- pytest coverage for the core modules

The next milestone is adding a Cross-Encoder reranker, measuring retrieval quality, and then connecting an LLM to complete the end-to-end RAG answer pipeline.
