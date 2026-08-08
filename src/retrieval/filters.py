from src.retrieval.models import RetrievedChunk
from src.retrieval.version_filter import (
    VersionInterval,
    chunk_version_interval,
    intervals_overlap,
)

"""
Post-retrieval filtering shared by dense/sparse/hybrid, so all three are
compared under the same filter semantics in evaluation.

Applied after candidate retrieval, not pushed into the index query itself
-- Chroma's `where` only does scalar equality/range on a single field, not
the interval-overlap logic version filtering needs, and BM25 has no
metadata filtering at all. A chunk with no version tag is kept rather
than dropped: missing metadata isn't evidence of a mismatch.
"""


def apply_filters(
    retrieved: list[RetrievedChunk],
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    kept = []
    for item in retrieved:
        if package is not None and item.chunk.package and item.chunk.package != package:
            continue
        if version_filter is not None:
            chunk_interval = chunk_version_interval(item.chunk.version)
            if chunk_interval is not None and not intervals_overlap(version_filter, chunk_interval):
                continue
        kept.append(item)

    return [
        RetrievedChunk(chunk=item.chunk, score=item.score, rank=rank)
        for rank, item in enumerate(kept, start=1)
    ]
