import pytest

from scripts.generate_pydantic_gold_set import (
    FROZEN_V1_QUERY_DIGEST,
    check_frozen_guard,
    query_digest,
)


def test_query_digest_deterministic_across_key_order():
    a = [{"query_id": "q1", "required_change_ids": ["c1", "c2"]}]
    b = [{"required_change_ids": ["c1", "c2"], "query_id": "q1"}]
    assert query_digest(a) == query_digest(b)


def test_query_digest_sensitive_to_content_drift():
    a = [{"query_id": "q1", "required_change_ids": ["c1"]}]
    b = [{"query_id": "q1", "required_change_ids": ["c1", "c2"]}]
    assert query_digest(a) != query_digest(b)


def test_frozen_guard_passes_on_matching_digest(monkeypatch):
    unfrozen_metadata = {"status": "human-reviewed / frozen"}
    matching_queries: list[dict] = []
    monkeypatch.setattr(
        "scripts.generate_pydantic_gold_set.FROZEN_V1_QUERY_DIGEST",
        query_digest(matching_queries),
    )
    check_frozen_guard(unfrozen_metadata, matching_queries)


def test_frozen_guard_raises_on_content_drift():
    frozen_metadata = {"status": "human-reviewed / frozen"}
    drifted_queries = [{"query_id": "new_query_not_in_frozen_v1"}]
    with pytest.raises(RuntimeError, match="Gold Set v1 is frozen"):
        check_frozen_guard(frozen_metadata, drifted_queries)


def test_frozen_guard_skips_check_when_not_frozen():
    pending_metadata = {"status": "pending_freeze"}
    check_frozen_guard(pending_metadata, [{"query_id": "anything"}])


def test_current_frozen_gold_queries_match_committed_digest():
    import json
    from pathlib import Path

    data = json.loads(
        Path("data/gold/pydantic_gold_queries.json").read_text(encoding="utf-8")
    )
    assert data["metadata"]["status"] == "human-reviewed / frozen"
    assert query_digest(data["queries"]) == FROZEN_V1_QUERY_DIGEST
