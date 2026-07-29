import numpy as np

from src.retriever import retrieve

"""
Test the retriever.

This script verifies that the retriever can:
- Retrieve the most relevant text chunk
- Retrieve multiple top-ranked text chunks
- Handle top_k values larger than the number of chunks
- Return an empty list for empty input
"""
def test_retrieve_most_similar_chunk():
    chunks = [
        "The office opens at 9 AM.",
        "Employees receive 15 vacation days.",
        "The cafeteria closes at 6 PM.",
    ]

    document_embeddings = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [0.7, 0.7],
    ])

    query_embedding = np.array([1.0, 0.0])

    result = retrieve(
        query_embedding,
        document_embeddings,
        chunks,
        top_k=1,
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