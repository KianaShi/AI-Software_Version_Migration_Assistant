import sqlite3
from pathlib import Path

from src.aggregation import linker
from src.entities import store
from src.entities.models import Evidence, generate_id
from src.extraction.change_extraction import extract_changes
from src.extraction.models import SourceDocument
from src.extraction.sources import parse_migration_guide, parse_official_docs, parse_release_note
from src.retrieval.chunking import chunk_document
from src.retrieval.dense_index import build_dense_index, get_collection
from src.retrieval.models import Chunk
from src.retrieval.sparse_index import BM25Index, build_sparse_index

"""
Build the Stage 7 benchmark corpus/indices for pydantic 1.10.x -> 2.x.

Runs the full pipeline built so far end to end over real (if hand-
condensed) migration facts:
  raw corpus text -> chunking -> Level 1 extraction -> Level 2 aggregation
  -> real change_id/evidence_id -> dense + sparse indices

No LLM involved anywhere. This is what "freeze a deterministic baseline"
means concretely: every id referenced by the gold set is something this
script actually produced by running the pipeline, not a hand-invented
placeholder.
"""

CORPUS_DIR = Path("data/corpus/pydantic")
PACKAGE = "pydantic"
DENSE_COLLECTION_NAME = "migration_chunks_pydantic"


def load_documents() -> list[SourceDocument]:
    return [
        parse_migration_guide(
            (CORPUS_DIR / "migration_guide.md").read_text(encoding="utf-8"),
            url="local://pydantic/migration_guide.md",
        ),
        parse_release_note(
            (CORPUS_DIR / "release_notes.md").read_text(encoding="utf-8"),
            url="local://pydantic/release_notes.md",
        ),
        parse_official_docs(
            (CORPUS_DIR / "concepts.md").read_text(encoding="utf-8"),
            url="local://pydantic/concepts.md",
        ),
    ]


def _find_owning_chunk(statement_text: str, chunks: list[Chunk]) -> Chunk | None:
    """
    Best-effort match from an extracted claim's raw_text back to the chunk
    it came from. chunking.py and change_extraction.py both split on
    headings/bullets/sentences, so this is normally an exact match.
    """
    for chunk in chunks:
        if chunk.text.strip() == statement_text.strip():
            return chunk
    for chunk in chunks:
        if statement_text.strip() in chunk.text or chunk.text.strip() in statement_text:
            return chunk
    return None


def run_pipeline() -> tuple[list[Chunk], sqlite3.Connection, dict]:
    documents = load_documents()

    if store.DEFAULT_DB_PATH.exists():
        store.DEFAULT_DB_PATH.unlink()  # rebuild from scratch each run (change_id inserts aren't idempotent)

    conn = store.get_connection()
    store.init_db(conn)

    all_chunks: list[Chunk] = []
    stats = {"documents": len(documents), "chunks": 0, "unresolved_changes": 0, "evidence_linked_to_chunk": 0}

    for document in documents:
        chunks = chunk_document(document, default_package=PACKAGE)
        all_chunks.extend(chunks)
        stats["chunks"] += len(chunks)

        unresolved_changes = extract_changes(document, default_package=PACKAGE)
        stats["unresolved_changes"] += len(unresolved_changes)

        for index, unresolved in enumerate(unresolved_changes):
            evidence = Evidence(
                evidence_id=generate_id(
                    "ev", document.document_id, str(index), unresolved.raw_text[:100]
                ),
                source_type=document.source_type,
                source_document_id=document.document_id,
                symbol_mentions=[unresolved.symbol],
                raw_text=unresolved.raw_text,
                external_refs=unresolved.external_refs,
            )

            linker.resolve_evidence(conn, evidence, unresolved)

            owning_chunk = _find_owning_chunk(unresolved.raw_text, chunks)
            if owning_chunk is not None:
                owning_chunk.evidence_id = evidence.evidence_id
                stats["evidence_linked_to_chunk"] += 1

    return all_chunks, conn, stats


def build_indices(chunks: list[Chunk]):
    collection = get_collection(DENSE_COLLECTION_NAME, reset=True)
    build_dense_index(chunks, collection)
    sparse_index = build_sparse_index(chunks)
    return collection, sparse_index


def main() -> None:
    chunks, conn, stats = run_pipeline()
    collection, sparse_index = build_indices(chunks)

    print("Corpus build complete.")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print(f"  dense collection count: {collection.count()}")
    print(f"  sparse index chunks: {sparse_index.n_docs}")

    change_count = conn.execute("SELECT COUNT(*) FROM change_records").fetchone()[0]
    link_count = conn.execute("SELECT COUNT(*) FROM evidence_links").fetchone()[0]
    cannot_link_count = conn.execute("SELECT COUNT(*) FROM cannot_link_constraints").fetchone()[0]
    print(f"  change_records: {change_count}")
    print(f"  evidence_links: {link_count}")
    print(f"  cannot_link_constraints: {cannot_link_count}")


if __name__ == "__main__":
    main()
