# Shakespeare RAG

> 🚧 **Work in Progress**  
> A structure-aware Shakespeare question-answering system with benchmark-driven evaluation and planned multi-agent failure recovery.

---

## ✨ Overview

Shakespeare's works are long, highly structured, and distributed across many plays, acts, scenes, speakers, and speeches. This project explores how Retrieval-Augmented Generation can answer questions about Shakespeare while grounding responses in the original texts.

Rather than relying entirely on high-level RAG frameworks, the core pipeline is implemented step by step in Python. This makes it possible to inspect and evaluate each stage, including document parsing, chunking, embedding generation, vector storage, retrieval, prompt construction, and answer generation.

The project currently includes a general RAG foundation, a Shakespeare-specific HTML loader, ChromaDB integration, and an automated evaluation benchmark loader.

The next stage focuses on importing the full MIT Shakespeare corpus, preserving literary metadata, evaluating retrieval quality, and extending the system into a failure-aware multi-agent workflow.

---

## 🧠 System Pipeline

```text
MIT Shakespeare HTML Corpus
            ↓
Structured HTML Parsing
            ↓
Work / Act / Scene / Speaker Metadata
            ↓
Structure-Aware Chunking
            ↓
Embedding Generation
            ↓
ChromaDB Vector Index
            ↓
Semantic Retrieval
            ↓
Evidence Verification
            ↓
Prompt Construction
            ↓
LLM Answer Generation
            ↓
Citation Validation
```

The planned agentic workflow will add planning, evidence checking, query rewriting, retries, critique, and execution tracing.

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
- ✅ Fixed-size text chunking
- ✅ Embedding generation using Sentence Transformers
- ✅ Semantic retrieval
- ✅ ChromaDB collection and storage modules
- ✅ Prompt builder
- ✅ MIT Shakespeare scene-level HTML parser
- ✅ Structured metadata extraction:
  - work
  - act
  - scene
  - speaker
  - speech
- ✅ Automated benchmark loading from multiple JSON files
- ✅ Five-play benchmark subset with 507 question-answer records
- ✅ Unit tests with pytest
- ⏳ Full MIT Shakespeare corpus ingestion
- ⏳ Structure-aware chunking
- ⏳ Metadata-aware vector storage
- ⏳ Retrieval evaluation
- ⏳ LLM response generation
- ⏳ Multi-agent planning and evidence verification
- ⏳ Query rewriting and retry logic
- ⏳ Citation validation
- ⏳ Interactive Shakespeare Q&A interface

---

## 📚 Data Sources

### Shakespeare Corpus

The project uses the HTML editions of Shakespeare's plays provided by the MIT Shakespeare project as the retrieval knowledge base.

- **Source:** TheMITTech/shakespeare
- **Repository:** `https://github.com/TheMITTech/shakespeare`
- **Usage:** Original play text used for parsing, metadata extraction, chunking, embedding generation, and retrieval

The corpus contains scene-level HTML files with identifiable play, act, scene, speaker, dialogue, and stage-direction structure.

Example source file:

```text
hamlet/hamlet.3.1.html
```

Parsed output:

```python
{
    "work": "hamlet",
    "act": 3,
    "scene": 1,
    "speaker": "HAMLET",
    "speech": "To be, or not to be..."
}
```

The external corpus is kept separate from this repository during development. A download or setup script will be added so users can obtain the corpus without committing the entire source repository.

### Evaluation Benchmark

Retrieval and answer-generation performance are evaluated using selected files from:

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

Each benchmark record may contain:

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

The benchmark files are used **only for evaluation** and are not inserted into the vector database. This separation prevents benchmark leakage.

---

## 📖 Knowledge Base Design

The Shakespeare corpus preserves literary structure wherever possible:

```text
Work
 └── Act
      └── Scene
           ├── Stage Direction
           └── Speech
                ├── Speaker
                └── Dialogue
```

The first parser version extracts individual speeches with metadata:

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
- citation validation
- benchmark evaluation
- multi-play coverage checking

Stage directions are detected separately and excluded from the speech records used by the current loader.

---

## 🔬 Retrieval Experiments

A major focus of the project is comparing retrieval strategies rather than treating retrieval as a black box.

### Baseline: Fixed-Size Chunking

```text
Document
   ↓
Fixed Character Windows
   ↓
Embedding
   ↓
Similarity Search
```

This strategy is simple but may split dialogue, speeches, scenes, or important literary context at arbitrary boundaries.

### Structure-Aware Chunking

```text
Play
  ↓
Act
  ↓
Scene
  ↓
Speech-Aware Chunk Groups
```

The structure-aware approach will preserve scene boundaries and combine nearby speeches without crossing unrelated scenes.

Planned comparison:

```text
Fixed-Size Chunking
        vs.
Structure-Aware Chunking
```

The goal is to determine whether literary structure improves retrieval accuracy, evidence quality, and citation reliability.

---

## 📊 Evaluation

The project uses an external Shakespeare QA benchmark rather than evaluating only with manually selected demo questions.

### Planned Retrieval Metrics

- Recall@1
- Recall@3
- Recall@5
- Mean Reciprocal Rank
- Retrieval latency
- Correct play rate
- Correct act and scene rate

For a benchmark record such as:

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

Because the benchmark includes category and difficulty labels, results can be analyzed by:

```text
Category
├── factual
├── interpretive
├── quote
└── scene
```

and:

```text
Difficulty
├── basic
├── intermediate
└── advanced
```

This will help identify where the system fails instead of reporting only one overall score.

---

## 🤖 Planned Multi-Agent Failure Recovery

The final system is planned as a failure-aware multi-agent workflow.

### Planned Agents

**Planner Agent**

- identifies the question type
- selects relevant plays or characters
- breaks complex comparisons into subqueries

**Retrieval Agent**

- calls the Shakespeare search tool
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
│   ├── sample.pdf
│   └── sample.txt
│
├── docs/
│   ├── architecture-day1.png
│   └── notes.md
│
├── src/
│   ├── benchmark_loader.py
│   ├── document_loader.py
│   ├── shakespeare_loader.py
│   ├── chunker.py
│   ├── embedding.py
│   ├── retriever.py
│   ├── vector_store.py
│   ├── prompt_builder.py
│   │
│   └── tools/
│       ├── __init__.py
│       └── shakespeare_search.py
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

- [x] TXT Document Loader
- [x] PDF Document Loader
- [x] Fixed-Size Text Chunking
- [x] Embedding Generation
- [x] Semantic Retriever
- [x] ChromaDB Storage Module
- [x] Prompt Builder
- [ ] LLM Integration

### Shakespeare Knowledge Base

- [x] Inspect MIT Shakespeare HTML structure
- [x] Parse work / act / scene metadata
- [x] Extract speaker and speech records
- [x] Exclude stage directions from speech records
- [x] Add Shakespeare loader tests
- [ ] Add automated corpus download script
- [ ] Import selected MIT Shakespeare plays
- [ ] Store complete metadata in ChromaDB
- [ ] Implement structure-aware chunking
- [ ] Build the full Shakespeare vector index

### Evaluation

- [x] Select five benchmark plays
- [x] Add 507 benchmark QA records
- [x] Implement automated benchmark loader
- [ ] Add benchmark loader tests
- [ ] Measure Recall@1 / Recall@3 / Recall@5
- [ ] Measure Mean Reciprocal Rank
- [ ] Measure retrieval latency
- [ ] Compare fixed-size and structure-aware chunking
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

The goal of this project is not only to create a working Shakespeare chatbot, but to build and evaluate a transparent retrieval system that can detect and recover from failure.

The project explores:

- how literary structure affects chunking
- how metadata affects retrieval
- how retrieval quality can be measured
- how benchmark leakage can be prevented
- how evidence can be validated before answer generation
- how multi-agent systems can recover from weak retrieval
- how execution traces can make agent behavior observable
- how retrieval and answer quality vary across question types and difficulty levels

The final system will provide a searchable Shakespeare research experience backed by original texts, structured citations, benchmark evaluation, and failure-aware agent execution.

---

## 📌 Status

> 🚧 **This project is actively under development.**

Current progress includes:

- a general RAG pipeline
- a scene-level MIT Shakespeare HTML parser
- structured speech metadata extraction
- ChromaDB storage and retrieval modules
- an automated benchmark loader
- a 507-question benchmark subset across five plays
- pytest coverage for the core modules

The next milestone is importing the MIT Shakespeare corpus, storing metadata-rich chunks in ChromaDB, and running the first Recall@K evaluation.