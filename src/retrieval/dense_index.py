from src.embedding import generate_embeddings
from src.retrieval.models import Chunk, RetrievedChunk
from src.vector_store import add_chunks, create_collection, reset_collection

"""
Dense retrieval baseline: thin wrapper over the existing embedding.py +
vector_store.py (ChromaDB) infra, specialized to Chunk objects.

Functions here take an already-obtained `collection`, matching
vector_store.py's own convention (add_chunks takes a collection, not a
name) -- get_collection() is the production convenience that wraps
create_collection()/reset_collection(); tests can pass any ChromaDB
collection (e.g. an EphemeralClient one) directly.
"""

DEFAULT_COLLECTION_NAME = "migration_chunks"


def get_collection(collection_name: str = DEFAULT_COLLECTION_NAME, reset: bool = True):
    if reset:
        reset_collection(collection_name)
    return create_collection(collection_name)


def _chunk_metadata(chunk: Chunk) -> dict:
    return {
        "source_document_id": chunk.source_document_id,
        "source_type": chunk.source_type,
        "package": chunk.package or "",
        "version": chunk.version or "",
        "symbols": ",".join(chunk.symbols),
        "evidence_id": chunk.evidence_id or "",
    }


def build_dense_index(chunks: list[Chunk], collection):
    if not chunks:
        return collection

    embeddings = generate_embeddings([c.text for c in chunks])
    add_chunks(
        collection=collection,
        document_name=DEFAULT_COLLECTION_NAME,
        chunks=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[_chunk_metadata(c) for c in chunks],
        ids=[c.chunk_id for c in chunks],
    )
    return collection


def query_dense(
    collection,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    top_k: int = 10,
    fetch_k: int | None = None,
) -> list[RetrievedChunk]:
    """
    fetch_k: how many raw candidates to pull from Chroma before any
    caller-side post-filtering (version overlap, package). Defaults to
    top_k so this behaves like a plain top-K query when used standalone;
    retrieval.py's filtered entrypoints pass a larger fetch_k.
    """
    n = fetch_k or top_k
    query_embedding = generate_embeddings([query_text])

    result = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=min(n, max(collection.count(), 1)),
        include=["distances"],
    )

    ids = result["ids"][0]
    distances = result["distances"][0]

    retrieved = []
    for rank, (chunk_id, distance) in enumerate(zip(ids, distances), start=1):
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        retrieved.append(RetrievedChunk(chunk=chunk, score=distance, rank=rank))

    return retrieved
