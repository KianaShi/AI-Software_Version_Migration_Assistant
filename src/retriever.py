from src.embedding import generate_embeddings

def retrieve(
    collection,
    question: str,
    top_k: int = 5,
    where: dict | None = None,
) -> list[dict]:
    question_embedding = generate_embeddings([question])

    query_args = {
        "query_embeddings": question_embedding.tolist(),
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if where:
        query_args["where"] = where

    result = collection.query(**query_args)

    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    return [
        {
            "text": document,
            "metadata": metadata,
            "distance": distance,
        }
        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        )
    ]