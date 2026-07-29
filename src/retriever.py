import numpy as np

"""
Retrieve the most relevant text chunks based on semantic similarity.

Args:
    query_embedding: Embedding vector of the user's query.
    document_embeddings: Embedding vectors of all document chunks.
    chunks: Original text chunks.

Returns:
    A list of the most relevant text chunks.
"""
def retrieve(
    query_embedding: np.ndarray,
    document_embeddings: np.ndarray,
    chunks: list[str],
    top_k: int = 3,
):
    
    similarities = []
    result = []
    for embedding in document_embeddings:
        score = np.dot(query_embedding, embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(embedding))
        similarities.append(score)
        
    order = np.argsort(similarities)[::-1]
    
    for index  in order[:top_k]:
        result.append(chunks[index])
        
    return result