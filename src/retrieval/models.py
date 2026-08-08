from dataclasses import dataclass, field

"""
Retrieval-layer types.

Chunk is a retrieval unit: an arbitrary text span plus enough metadata to
filter and to trace back to where it came from. It is deliberately not
the same type as src.entities.models.Evidence -- a chunk is produced at
index time by chunking.py, before (and independent of) whether Level 1
extraction has ever looked at it. evidence_id is a forward-looking hook:
once/if an Evidence gets created from this chunk's text, its
embedding_id can point back at chunk_id, and this field can be filled in
to point the other way. Nothing in this pass wires that up automatically.
"""


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_document_id: str
    source_type: str  # src.entities.models.SourceType value
    provenance: str
    package: str | None = None
    version: str | None = None  # ambient, normalized (see extraction.version_normalization)
    symbols: list[str] = field(default_factory=list)  # normalized Symbol.name values found in text
    evidence_id: str | None = None  # hook: filled in once/if Level 1 has run on this chunk


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float  # native to whichever retriever produced it; only rank order is comparable across retrievers
    rank: int
