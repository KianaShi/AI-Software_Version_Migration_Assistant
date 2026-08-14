import pytest

from src.retrieval.models import Chunk, RetrievedChunk
from src.retrieval.reranker import rerank

"""
Stage 8B1: tests the rerank() logic (score->sort->slice->rebuild) in
isolation from the real Qwen3-Reranker-0.6B model -- loading 1.2GB of
weights on every test run would make the fast default suite slow and
network-dependent. A stub model (any object with .predict(pairs) ->
scores) exercises the same code path deterministically; the real
model's actual reranking quality is validated by
scripts/run_ranking_ablation.py against the real gold set instead.
"""


class _StubModel:
    def __init__(self, score_by_text: dict[str, float]):
        self.score_by_text = score_by_text
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.calls.append(pairs)
        return [self.score_by_text[doc_text] for _query, doc_text in pairs]


def _chunk(chunk_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=chunk_id,
            text=text,
            source_document_id="doc",
            source_type="release_note",
            provenance="test",
        ),
        score=0.0,
        rank=0,
    )


def test_rerank_reorders_by_model_score_not_input_order():
    candidates = [_chunk("a", "low relevance"), _chunk("b", "high relevance"), _chunk("c", "medium relevance")]
    model = _StubModel({"low relevance": 0.1, "high relevance": 0.9, "medium relevance": 0.5})

    results = rerank("some query", candidates, output_k=3, model=model)

    assert [r.chunk.chunk_id for r in results] == ["b", "c", "a"]


def test_rerank_slices_to_output_k():
    candidates = [_chunk("a", "x"), _chunk("b", "y"), _chunk("c", "z")]
    model = _StubModel({"x": 0.1, "y": 0.9, "z": 0.5})

    results = rerank("q", candidates, output_k=2, model=model)

    assert len(results) == 2
    assert [r.chunk.chunk_id for r in results] == ["b", "c"]


def test_rerank_reassigns_rank_field_sequentially():
    candidates = [_chunk("a", "x"), _chunk("b", "y")]
    model = _StubModel({"x": 0.1, "y": 0.9})

    results = rerank("q", candidates, output_k=2, model=model)

    assert [r.rank for r in results] == [1, 2]
    assert results[0].score == 0.9
    assert results[1].score == 0.1


def test_rerank_pairs_query_with_each_candidate_text():
    candidates = [_chunk("a", "chunk text A"), _chunk("b", "chunk text B")]
    model = _StubModel({"chunk text A": 0.2, "chunk text B": 0.8})

    rerank("the query", candidates, output_k=2, model=model)

    assert model.calls == [[("the query", "chunk text A"), ("the query", "chunk text B")]]


def test_rerank_empty_candidates_returns_empty_without_calling_model():
    model = _StubModel({})

    results = rerank("q", [], output_k=5, model=model)

    assert results == []
    assert model.calls == []


def test_rerank_negative_output_k_raises_even_with_empty_candidates():
    # output_k<0 must be rejected before the empty-candidates early
    # return -- otherwise it silently succeeds with [] instead of
    # surfacing the caller's bug, and with non-empty candidates
    # scored[:output_k] under a negative index would silently drop
    # items from the end rather than error at all.
    model = _StubModel({})

    with pytest.raises(ValueError):
        rerank("q", [], output_k=-1, model=model)


def test_rerank_negative_output_k_raises_with_candidates():
    candidates = [_chunk("a", "x")]
    model = _StubModel({"x": 0.5})

    with pytest.raises(ValueError):
        rerank("q", candidates, output_k=-1, model=model)


class _WrongScoreCountModel:
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        return [0.5] * (len(pairs) - 1) if pairs else []


def test_rerank_raises_if_model_returns_wrong_number_of_scores():
    candidates = [_chunk("a", "x"), _chunk("b", "y")]
    model = _WrongScoreCountModel()

    with pytest.raises(ValueError):
        rerank("q", candidates, output_k=2, model=model)
