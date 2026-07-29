import numpy as np
from src.embedding import generate_embeddings

"""
Retrieve the most relevant text chunks.

This function:
- Computes cosine similarity between the query and document embeddings
- Ranks document chunks by similarity score
- Returns the top-k most relevant text chunks
"""
def test_generate_embeddings():
    chunks = [
        "The office opens at 9 AM.",
        "Employees receive 15 vacation days.",
    ]

    embeddings = generate_embeddings(chunks)
    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape == (2, 384)