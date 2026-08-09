import math
from dataclasses import dataclass, field
from typing import Callable

"""
Retrieval evaluation harness.

The metric functions (recall_at_k, mrr, ndcg_at_k) only ever see a list
of item ids -- they don't know or care whether an id is a chunk_id,
change_id, or evidence_id. GoldQuery keeps two separate label lists,
deliberately not merged into one:

- required_change_ids: which changes a correct answer to this migration
  question must cover. Scored via resolve_to_ids() mapping a chunk-id
  ranking down through chunk.evidence_id -> evidence_links -> change_id
  (deduplicated, first occurrence keeps its rank). This is the basis for
  Migration Chain Recall later -- a new metric function over the same
  resolved id lists, not a re-annotation of the gold set.
- relevant_evidence_ids: which specific evidence/chunks are good support
  for the answer, independent of which change they resolve to. Scored the
  same way but through a chunk_id -> [evidence_id] resolver instead.

evaluate_queries() takes whichever resolver and whichever GoldQuery
attribute name the caller wants scored, so the same function runs both
views without knowing anything about the real Level 1/2 pipeline that
produced the resolver's mapping.
"""


@dataclass
class GoldQuery:
    query_id: str
    query_text: str
    query_type: str = ""
    from_version: str | None = None
    to_version: str | None = None
    required_change_ids: list[str] = field(default_factory=list)
    relevant_evidence_ids: list[str] = field(default_factory=list)
    # Stage 8A: chunk_ids (not evidence_ids -- stability facts don't go
    # through Level 1 extraction, see docs/entity-aggregation-log.md
    # Stage 8A feasibility note) backing a negative query's "nothing
    # changed" claim. Optional/empty for non-negative queries.
    stability_evidence_ids: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    query_id: str
    recall_at_5: float
    recall_at_10: float
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float


def recall_at_k(retrieved_ids: list[str], required_ids: list[str], k: int) -> float:
    if not required_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    covered = sum(1 for r in required_ids if r in top_k)
    return covered / len(required_ids)


def mrr(retrieved_ids: list[str], required_ids: list[str]) -> float:
    required = set(required_ids)
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in required:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], required_ids: list[str], k: int) -> float:
    required = set(required_ids)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item_id in enumerate(retrieved_ids[:k], start=1)
        if item_id in required
    )
    ideal_hits = min(len(required), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def resolve_to_change_ids(
    retrieved_chunk_ids: list[str], chunk_to_change_ids: dict[str, list[str]]
) -> list[str]:
    """
    Chunk-id ranking -> deduplicated item-id ranking (first occurrence
    keeps its rank). Named for its original change_id use case; the same
    function scores relevant_evidence_ids too when given a chunk_id ->
    [evidence_id] resolver instead -- it only ever sees opaque ids.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    for chunk_id in retrieved_chunk_ids:
        for item_id in chunk_to_change_ids.get(chunk_id, []):
            if item_id not in seen_set:
                seen_set.add(item_id)
                seen.append(item_id)
    return seen


def evaluate_queries(
    gold_queries: list[GoldQuery],
    run_query: Callable[[str], list[str]],
    chunk_to_change_ids: dict[str, list[str]],
    required_ids_attr: str = "required_change_ids",
) -> list[EvaluationResult]:
    """
    run_query(query_text) -> ranked list of chunk_ids. Swap it for a
    dense/sparse/hybrid retriever to compare them under the same gold set.

    chunk_to_change_ids: despite the name (kept for backward compatibility),
    this resolver can map to any item id space -- pass a chunk_id ->
    [evidence_id] resolver plus required_ids_attr="relevant_evidence_ids"
    to score evidence-level Recall@K/MRR/nDCG instead of change-level.
    """
    results = []
    for gold in gold_queries:
        retrieved_chunk_ids = run_query(gold.query_text)
        covered_ids = resolve_to_change_ids(retrieved_chunk_ids, chunk_to_change_ids)
        required_ids = getattr(gold, required_ids_attr)

        results.append(
            EvaluationResult(
                query_id=gold.query_id,
                recall_at_5=recall_at_k(covered_ids, required_ids, 5),
                recall_at_10=recall_at_k(covered_ids, required_ids, 10),
                mrr=mrr(covered_ids, required_ids),
                ndcg_at_5=ndcg_at_k(covered_ids, required_ids, 5),
                ndcg_at_10=ndcg_at_k(covered_ids, required_ids, 10),
            )
        )
    return results


def mean_recall_at_k(results: list[EvaluationResult], k: int) -> float:
    values = [r.recall_at_5 if k == 5 else r.recall_at_10 for r in results]
    return sum(values) / len(values) if values else 0.0
