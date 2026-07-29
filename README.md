# 🤖 RAG Chatbot

> 🚧 **Work in Progress**  
> A Retrieval-Augmented Generation (RAG) chatbot built from scratch to learn modern LLM application development.

---

## ✨ Overview

This project is a personal learning journey focused on understanding how Retrieval-Augmented Generation (RAG) systems work from the ground up.

Rather than relying on high-level frameworks, each component is implemented step by step to better understand the complete RAG pipeline, including document loading, text chunking, embedding generation, semantic retrieval, prompt construction, and LLM integration.

---

## 🚀 Current Features

- ✅ TXT document loader
- ✅ PDF document loader
- ✅ Fixed-size text chunking
- ✅ Embedding generation using Sentence Transformers
- ✅ Semantic retrieval using cosine similarity
- ✅ Unit tests with pytest
- ⏳ Vector database integration
- ⏳ Prompt builder
- ⏳ LLM response generation
- ⏳ Chat interface

---

## 🛠️ Tech Stack

- Python
- PyPDF
- Pytest
- NumPy
- Sentence Transformers
- ChromaDB *(planned)*
- OpenAI API *(planned)*

---

## 📂 Project Structure

```text
rag-chatbot/

├── data/
├── docs/
├── src/
│   ├── document_loader.py
│   ├── chunker.py
│   ├── embedding.py
│   ├── retriever.py
│   ├── vector_store.py
│   └── ...
│
├── tests/
│
├── README.md
└── requirements.txt
```

---

## 📋 Roadmap

- [x] Document Loader
- [x] Text Chunking
- [x] Embedding Generation
- [x] Semantic Retriever
- [ ] Vector Database Integration
- [ ] Prompt Builder
- [ ] LLM Integration
- [ ] Interactive Chatbot

---

## 🎯 Goal

The goal of this project is to build a complete Retrieval-Augmented Generation chatbot while gaining a deep understanding of each component in a modern LLM application.

---

## 📌 Status

> 🚧 This project is actively under development.

New features, tests, and improvements will be added as the project evolves.