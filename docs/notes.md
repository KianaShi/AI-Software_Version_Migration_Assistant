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

## Progress

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