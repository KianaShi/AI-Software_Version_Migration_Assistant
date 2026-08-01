from sentence_transformers import SentenceTransformer
import numpy as np


MODEL = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embeddings(chunks: list[str]) -> np.ndarray:
    """
    Generate vector embeddings for text chunks.
    
    Args: A list of chunks.
    Returns: ndarray of the chunks.
    """
    embeddings = MODEL.encode(chunks)
    return embeddings

def generate_query_embedding(question: str) -> np.ndarray:
    return MODEL.encode([question])