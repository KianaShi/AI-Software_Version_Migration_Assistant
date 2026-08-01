## What is RAG?

Retrieve information first, then let LLM generate answers.

## Chunking concern

Chunking may be inaccurate if important context is split across chunks.

Possible solutions include paragraph-based splitting, overlap, and tuning chunk size.

## What does embedding do?

Embedding converts text into vectors. Similar meanings are represented by vectors that are close to each other.

This allows the system to find relevant information even when different words are used.

## Why use vector databases?

Vector databases store embeddings and make similarity search efficient.

When a user asks a question, the question is also converted into a vector. The system then finds the most similar chunks and sends them to the LLM.

## What does the LLM do?

The LLM mainly organizes retrieved information into natural language.

In a RAG system, retrieval provides knowledge, while the LLM provides expression and reasoning.

Incorrect retrieval may lead the LLM to generate incorrect answers, even if the model itself is powerful.

## Personal Thoughts

My intuition is that a vector database and retriever are somewhat similar to a HashMap, but with fuzzy matching instead of exact matching.

A HashMap returns a value when the key matches exactly. In contrast, a retriever returns the top-k chunks whose vectors are closest to the query vector.

This analogy is not perfectly accurate, but it helps me understand how retrieval works.

# rag-chatbot
Personal project for learning RAG and LLM applications.


### Day 1

- Understand the RAG pipeline
- Learn chunking and embeddings
- Learn vector databases and retrievers
- Document key concepts

### Day 2

- Design the document loader interface
- Implement `load_document(filepath)`
- Return `list[str]`
- Remove empty lines
- Normalize different document formats to the same output structure
- Learn the difference between `print()` and `return`
- Learn list comprehension

### Day 3

- Add support for loading PDF documents with `pypdf`
- Support both `.txt` and `.pdf` files through one `load_document()` interface
- Use `with open()` and UTF-8 encoding for safer text-file handling
- Ignore empty lines and normalize output to `list[str]`
- Add loader tests for TXT and PDF files

### Day 4 

- Implemented a fixed-size text chunking module.
- Combined multiple text lines into configurable chunks.
- Preserved remaining lines when the final chunk is smaller than the chunk size.
- Added unit tests using pytest.

Unit Tests:
- Basic chunking (7 lines → 2 chunks)
- Less than one chunk
- Exactly one chunk
- Empty input

### Day 5

- Implemented an embedding generation module using Sentence Transformers.
- Used the pre-trained `all-MiniLM-L6-v2` model to convert text chunks into vector embeddings.
- Returned embeddings as a NumPy array for compatibility with future vector search.
- Added unit tests using pytest.

Unit Tests:
- Output type is `numpy.ndarray`
- Correct embedding shape `(2, 384)`
- One embedding generated for each input chunk

Notes:
- Learned how pre-trained embedding models encode text into numerical vectors.
- Learned that semantic similarity is based on vector representations rather than exact words.
- Learned that embedding models return NumPy arrays instead of Python lists.

### Day 6

- Implemented a retriever using cosine similarity.
- Compared a query embedding with document embeddings.
- Ranked document chunks based on similarity scores.
- Returned the top-k most relevant text chunks.
- Added unit tests using pytest.

Unit Tests:
- Retrieve the most similar chunk
- Retrieve multiple top-ranked chunks
- Handle `top_k` greater than the number of chunks
- Handle empty input

### Day 7

- Implemented a prompt builder for the RAG pipeline.
- Combined retrieved text chunks into a single context.
- Built prompts using Python f-strings and triple-quoted strings.
- Added instructions for the language model to answer using only the provided context.
- Added unit tests using pytest.

Unit Tests:
- Include the user's question in the prompt
- Include retrieved context chunks
- Handle an empty context list

### Day 8

- Integrated ChromaDB as the vector store for the RAG pipeline.
- Created and managed persistent ChromaDB collections.
- Stored document chunks, embeddings, IDs, and metadata.
- Generated unique IDs for each document chunk.
- Added metadata to record the source document.
- Added unit tests using pytest.

Unit Tests:
- Create a ChromaDB collection
- Add document chunks and embeddings
- Verify the number of stored records
- Verify generated chunk IDs
- Verify stored metadata
- Verify stored documents

### Day 9
End-to-End RAG Pipeline
Connected all previously implemented modules into a complete RAG pipeline.
Embedded the user's question using the same embedding model.
Retrieved the most relevant document chunks from the vector store.
Built prompts by combining retrieved context with the user's question.
Sent the final prompt to the language model.
Verified that the entire RAG workflow runs end-to-end.

Unit Tests:

End-to-end retrieval pipeline
Question embedding generation
Prompt construction with retrieved context
Empty retrieval results
Multiple retrieved chunks

### Day 10
Evaluation and Testing
Added a retrieval demo for manual evaluation.
Tested the pipeline using natural language questions.
Printed retrieved metadata, similarity scores, and retrieved text.
Verified that ChromaDB returns the expected number of results.
Evaluated retrieval quality on simple factual questions.

Notes:

Learned that retrieval quality cannot be measured only by whether the code runs.
Retrieval results need manual inspection before connecting an LLM.

### Day 11
Building a Real Knowledge Base
Replaced sample documents with the Shakespeare corpus.
Implemented a dedicated HTML parser for Shakespeare plays.
Extracted speakers, speeches, acts, and scenes.
Ignored stage directions.
Added metadata for each speech.
Added unit tests for HTML parsing.

Unit Tests:

Speaker extraction
Speech extraction
Metadata extraction
Stage direction removal

Notes:

Real-world datasets require task-specific preprocessing.
Different document formats often need different loaders.

### Day 12
Building the Shakespeare Vector Store
Parsed all Shakespeare HTML files.
Generated embeddings for every speech.
Stored embeddings, metadata, and IDs in ChromaDB.
Skipped non-scene HTML files during indexing.
Indexed 986 speeches successfully.

Notes:

Built an offline document ingestion pipeline.
Learned the difference between indexing and querying.

### Day 13
Retrieval Evaluation and Chunking Optimization
Evaluated retrieval quality using real Shakespeare questions.
Observed that speech-level chunking sometimes lost conversational context.
Identified retrieval failures caused by isolated dialogue segments.
Designed a context-aware chunking strategy using neighboring speeches.
Planned future comparison between different chunking strategies.

Notes:

Chunking strategy directly affects retrieval quality.
Semantic chunking should depend on document structure rather than using a fixed strategy for every corpus.