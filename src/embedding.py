from sentence_transformers import SentenceTransformer
import numpy as np

"""
Generate vector embeddings for text chunks.

This module converts text chunks into numerical vectors
that can later be used for semantic similarity search.
"""

MODEL = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embeddings(chunks: list[str]) -> np.ndarray:
    embeddings = MODEL.encode(chunks)
    return embeddings