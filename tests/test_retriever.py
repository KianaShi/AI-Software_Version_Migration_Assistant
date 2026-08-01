from src.retriever import retrieve
import numpy as np
from src.vector_store import create_collection, add_chunks
"""
Test the retriever.

This script verifies that the retriever can:
- Retrieve the most relevant text chunk
- Retrieve multiple top-ranked text chunks
- Handle top_k values larger than the number of chunks
- Return an empty list for empty input
"""
def test_retrieve_returns_relevant_chunks():
    chunks = [
    "Solar energy uses sunlight.",
    "Wind energy uses moving air.",
    "Cats are common household pets.",
    ]
    collection = create_collection("test")
    add_chunks(collection, "sample.txt", )

    result = retrieve(
    collection,
    "What energy comes from the sun?",
    top_k=2,
)

    assert result == ["The office opens at 9 AM."]

def test_retrieve_top_two_chunks():
    chunks = [
        "Chunk A",
        "Chunk B",
        "Chunk C",
    ]

    document_embeddings = np.array([
        [1.0, 0.0],
        [0.8, 0.2],
        [0.0, 1.0],
    ])

    query_embedding = np.array([1.0, 0.0])

    result = retrieve(
        query_embedding,
        document_embeddings,
        chunks,
        top_k=2,
    )

    assert result == ["Chunk A", "Chunk B"]

def test_top_k_greater_than_number_of_chunks():
    chunks = [
        "Chunk A",
        "Chunk B",
        "Chunk C",
    ]

    document_embeddings = np.array([
        [1.0, 0.0],
        [0.8, 0.2],
        [0.0, 1.0],
    ])

    query_embedding = np.array([1.0, 0.0])

    result = retrieve(
        query_embedding,
        document_embeddings,
        chunks,
        top_k=10,
    )

    assert len(result) == 3
    assert result == ["Chunk A", "Chunk B", "Chunk C"]

def test_retrieve_empty_input():
    chunks = []
    document_embeddings = np.empty((0, 2))
    query_embedding = np.array([1.0, 0.0])

    result = retrieve(
        query_embedding,
        document_embeddings,
        chunks,
        top_k=3,
    )

    assert result == []