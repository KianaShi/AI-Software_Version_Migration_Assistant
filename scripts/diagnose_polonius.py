from src.vector_store import create_collection


COLLECTION_NAME = "shakespeare"
TARGET_PHRASES = [
    "Dead, for a ducat, dead",
    "How now! a rat",
    "What hast thou done",
]


def main() -> None:
    collection = create_collection(COLLECTION_NAME)

    print(f"Collection count: {collection.count()}")
    print("-" * 80)

    all_records = collection.get(
        include=["documents", "metadatas"]
    )

    documents = all_records.get("documents", [])
    metadatas = all_records.get("metadatas", [])
    ids = all_records.get("ids", [])

    matches_found = 0

    for record_id, document, metadata in zip(ids, documents, metadatas):
        normalized_document = document.lower()

        matched_phrases = [
            phrase
            for phrase in TARGET_PHRASES
            if phrase.lower() in normalized_document
        ]

        if not matched_phrases:
            continue

        matches_found += 1

        print(f"\nMatch {matches_found}")
        print(f"ID: {record_id}")
        print(f"Metadata: {metadata}")
        print(f"Matched phrases: {matched_phrases}")
        print("Text:")
        print(document)
        print("-" * 80)

    if matches_found == 0:
        print("No target text was found in ChromaDB.")
        print(
            "The problem is probably in corpus parsing, chunking, "
            "or vector-store ingestion."
        )
    else:
        print(f"\nFound {matches_found} matching stored chunks.")
        print(
            "The evidence exists in ChromaDB. If semantic retrieval still "
            "cannot return it, the problem is in retrieval rather than ingestion."
        )


if __name__ == "__main__":
    main()