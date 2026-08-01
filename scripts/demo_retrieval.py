from src.retriever import retrieve
from src.vector_store import create_collection

COLLECTION_NAME = "shakespeare"


def main() -> None:
    collection = create_collection(COLLECTION_NAME)

    question = "Who killed Polonius?"

    print(f"Question: {question}")
    print("-" * 80)

    results = retrieve(
        collection=collection,
        question=question,
        top_k=20,
    )

    for i, result in enumerate(results, start=1):
        print(f"\nResult {i}")
        print("Metadata:", result["metadata"])
        print("Distance:", result["distance"])
        print(result["text"])


if __name__ == "__main__":
    main()