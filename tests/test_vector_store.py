import chromadb
import numpy as np
from src.vector_store import add_chunks

"""
Test the ChromaDB vector store.

This script verifies that the vector store can:
- Create a collection
- Add document chunks and embeddings
- Store the expected number of records
"""

def test_add_chunks():
    client = chromadb.EphemeralClient()

    collection = client.get_or_create_collection(
        name="test_collection"
    )

    chunks = [
        "Solar energy uses sunlight.",
        "Wind energy uses moving air.",
    ]

    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ])

    add_chunks(
        collection=collection,
        document_name="sample.pdf",
        chunks=chunks,
        embeddings=embeddings,
    )
    
    result = collection.get()

    assert collection.count() == 2
    assert result["ids"][0] == "sample_pdf_chunk_0"
    assert result["metadatas"][0]["source"] == "sample.pdf"
    assert result["documents"][0] == "Solar energy uses sunlight."
    assert result["ids"][1] == "sample_pdf_chunk_1"