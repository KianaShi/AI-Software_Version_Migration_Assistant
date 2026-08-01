from pathlib import Path

from src.embedding import generate_embeddings
from src.shakespeare_loader import shakespeare_loader
from src.vector_store import (
    add_chunks,
    create_collection,
    reset_collection,
)

CORPUS_DIRECTORY = Path("data/corpus/shakespeare")
COLLECTION_NAME = "shakespeare"
RESET_COLLECTION = True

def prepare_speeches(speeches: list[dict]) -> tuple[list[str], list[dict]]:
    """
    Convert parsed Shakespeare speeches into chunks and metadata.

    Each speech is treated as one semantic chunk.

    Args:
        speeches: Parsed speech dictionaries returned by
            shakespeare_loader().

    Returns:
        A tuple containing:
        - chunk texts
        - metadata dictionaries
    """
    chunks = []
    metadatas = []

    for index, speech in enumerate(speeches):
        speaker = speech["speaker"].strip()
        text = speech["speech"].strip()

        if not text:
            continue

        start = max(0, index - 1)
        end = min(len(speeches), index + 2)

        window = speeches[start:end]

        metadata = {
            "speaker": speaker,
            "work": speech["work"],
            "act": speech["act"],
            "scene": speech["scene"],
        }
        
        chunk = "\n\n".join(
            f'{item["speaker"]}: {item["speech"]}'
            for item in window
            )

        chunks.append(chunk)
        metadatas.append(metadata)

    return chunks, metadatas

def ingest_file(collection, file_path: Path) -> int:
    """
    Load one Shakespeare HTML file, generate embeddings,
    and store the speeches in ChromaDB.

    Args:
        collection: The ChromaDB collection.
        file_path: Path to one Shakespeare HTML file.

    Returns:
        The number of chunks stored.
    """
    speeches = shakespeare_loader(str(file_path))

    if not speeches:
        print(f"Skipped {file_path.name}: no speeches found.")
        return 0

    chunks, metadatas = prepare_speeches(speeches)

    if not chunks:
        print(f"Skipped {file_path.name}: no valid text found.")
        return 0

    embeddings = generate_embeddings(chunks)

    add_chunks(
        collection=collection,
        document_name=file_path.name,
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Stored {len(chunks)} speeches from {file_path.name}.")

    return len(chunks)

def main() -> None:
    """
    Build the Shakespeare vector store from all scene HTML files.
    """
    if not CORPUS_DIRECTORY.exists():
        raise FileNotFoundError(
            f"Corpus directory not found: {CORPUS_DIRECTORY}"
        )

    html_files = []

    for file_path in sorted(CORPUS_DIRECTORY.rglob("*.html")):
        parts = file_path.stem.split(".")

        if len(parts) != 3:
            print(f"Skipping non-scene file: {file_path.name}")
            continue

        work, act, scene = parts

        if not act.isdigit() or not scene.isdigit():
            print(f"Skipping invalid scene file: {file_path.name}")
            continue

        html_files.append(file_path)

    if not html_files:
        raise FileNotFoundError(
            f"No scene HTML files found in {CORPUS_DIRECTORY}"
        )
        
    if RESET_COLLECTION:
        reset_collection(COLLECTION_NAME)
        
    collection = create_collection(COLLECTION_NAME)

    total_chunks = 0

    for file_path in html_files:
        total_chunks += ingest_file(
            collection=collection,
            file_path=file_path,
        )

    print()
    print("Vector store build completed.")
    print(f"Processed files: {len(html_files)}")
    print(f"Stored speeches: {total_chunks}")
    print(f"Collection count: {collection.count()}")


if __name__ == "__main__":
    main()