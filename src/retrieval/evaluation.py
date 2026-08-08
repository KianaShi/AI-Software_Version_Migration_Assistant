import math
from dataclasses import dataclass, field
from typing import Callable

"""
Retrieval evaluation harness.

The metric functions (recall_at_k, mrr, ndcg_at_k) only ever see a list
of item ids -- they don't know or care whether an id is a chunk_id or a
change_id. GoldQuery.required_change_ids is annotated at the change_id
level per the design brief ("必须覆盖的 change_id 列表"), and
resolve_to_change_ids() maps a chunk-id ranking down to a deduplicated
change-id ranking via an injected resolver. Nothing here assumes that
resolver is backed by the real Level 1/2 pipeline -- it isn't, yet (see
retrieval/models.py's Chunk.evidence_id hook) -- so evaluate_queries()
takes it as a plain dict/callable. This keeps today's Recall@K runnable
without the full pipeline wired, and means upgrading to Migration Chain
Recall later is a new metric function, not a re-annotation of the gold
set.
"""


@dataclass
class GoldQuery:
    query_id: str
    query_text: str
    required_change_ids: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    query_id: str
    recall_at_5: float
    recall_at_10: float
    mrr: float
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
    """Chunk-id ranking -> deduplicated change-id ranking (first occurrence wins the rank)."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for chunk_id in retrieved_chunk_ids:
        for change_id in chunk_to_change_ids.get(chunk_id, []):
            if change_id not in seen_set:
                seen_set.add(change_id)
                seen.append(change_id)
    return seen


def evaluate_queries(
    gold_queries: list[GoldQuery],
    run_query: Callable[[str], list[str]],
    chunk_to_change_ids: dict[str, list[str]],
) -> list[EvaluationResult]:
    """
    run_query(query_text) -> ranked list of chunk_ids. Swap it for a
    dense/sparse/hybrid retriever to compare them under the same gold set.
    """
    results = []
    for gold in gold_queries:
        retrieved_chunk_ids = run_query(gold.query_text)
        covered_change_ids = resolve_to_change_ids(retrieved_chunk_ids, chunk_to_change_ids)

        results.append(
            EvaluationResult(
                query_id=gold.query_id,
                recall_at_5=recall_at_k(covered_change_ids, gold.required_change_ids, 5),
                recall_at_10=recall_at_k(covered_change_ids, gold.required_change_ids, 10),
                mrr=mrr(covered_change_ids, gold.required_change_ids),
                ndcg_at_10=ndcg_at_k(covered_change_ids, gold.required_change_ids, 10),
            )
        )
    return results


def mean_recall_at_k(results: list[EvaluationResult], k: int) -> float:
    values = [r.recall_at_5 if k == 5 else r.recall_at_10 for r in results]
    return sum(values) / len(values) if values else 0.0
