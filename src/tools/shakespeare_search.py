from src.retriever import retrieve


def search_shakespeare(
    collection,
    question: str,
    top_k: int = 5,
    work: str | None = None,
    act: int | None = None,
    scene: int | None = None,
) -> list[dict]:
    filters = {}

    if work is not None:
        filters["work"] = work

    if act is not None:
        filters["act"] = act

    if scene is not None:
        filters["scene"] = scene

    where = filters or None

    return retrieve(
        collection=collection,
        question=question,
        top_k=top_k,
        where=where,
    )