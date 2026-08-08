import chromadb

"""
Store and retrieve document chunks using ChromaDB.

This module:
- Creates a persistent ChromaDB client
- Manages a collection for document chunks
- Supports vector storage and semantic search
"""

def get_client():
    """
    Create the persistent ChromaDB client.

    Returns:
        A persistent ChromaDB client.
    """
    return chromadb.PersistentClient(path="chroma_db")


def create_collection(collection_name: str):
    """
    Create or load a persistent ChromaDB collection.

    Args:
        collection_name: Name of the collection.

    Returns:
        A ChromaDB collection used to store document chunks.
    """
    client = get_client()

    collection = client.get_or_create_collection(
        name=collection_name
    )

    return collection

def add_chunks(
    collection,
    document_name: str,
    chunks: list[str],
    embeddings,
    metadatas: list[dict],
    ids: list[str] | None = None,
):
    """
    Add document chunks and their embeddings to a ChromaDB collection.

    Args:
        collection: The ChromaDB collection.
        document_name: Name of the source document.
        chunks: Text chunks to be stored.
        embeddings: Embedding vectors corresponding to each chunk.
        metadatas: Metadata associated with each chunk.
        ids: Explicit ids for each chunk. When omitted, ids are derived
            from document_name (existing behavior, unchanged).
    """
    if ids is None:
        safe_name = document_name.replace(".", "_")
        ids = [f"{safe_name}_chunk_{i}" for i in range(len(chunks))]

    collection.add(
    ids=ids,
    documents=chunks,
    embeddings=embeddings.tolist(),
    metadatas= metadatas
    )
    
def reset_collection(collection_name: str) -> None:
    """
    Delete an existing ChromaDB collection if it exists.

    Args:
        collection_name: Name of the collection.
    """
    client = get_client()

    try:
        client.delete_collection(collection_name)
        print(f"Deleted collection: {collection_name}")
    except Exception:
        print(f"Collection '{collection_name}' does not exist.")