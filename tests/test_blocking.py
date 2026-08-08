from pathlib import Path

from src.aggregation import blocking
from src.entities import store
from src.entities.models import ChangeRecord, Symbol

"""
Test Level 2 candidate generation (blocking).

Verifies that blocking narrows candidates purely by symbol identity
(+ optional version_to pre-filter) and does not exclude candidates with an
unknown version_to.
"""


def _make_conn():
    conn = store.get_connection(Path(":memory:"))
    store.init_db(conn)
    return conn


def _make_change(change_id, symbol, version_to="3.0"):
    return ChangeRecord(
        symbol=symbol,
        version_from="2.0",
        version_to=version_to,
        change_type="REMOVED",
        summary="summary",
        external_refs=[],
        change_id=change_id,
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        raw_text="text",
    )


def test_generate_candidates_matches_symbol_only():
    conn = _make_conn()
    target_symbol = Symbol(name="requests.Session.verify", package="requests")
    store.insert_change_record(conn, _make_change("chg_1", target_symbol))
    store.insert_change_record(
        conn, _make_change("chg_2", Symbol(name="other.Thing", package="requests"))
    )

    candidates = blocking.generate_candidates(conn, target_symbol)

    assert [c.change_id for c in candidates] == ["chg_1"]


def test_generate_candidates_keeps_unknown_version():
    conn = _make_conn()
    symbol = Symbol(name="requests.Session.verify", package="requests")
    store.insert_change_record(conn, _make_change("chg_1", symbol, version_to=None))

    candidates = blocking.generate_candidates(conn, symbol, version_to="3.0")

    assert [c.change_id for c in candidates] == ["chg_1"]


def test_generate_candidates_excludes_known_different_version():
    conn = _make_conn()
    symbol = Symbol(name="requests.Session.verify", package="requests")
    store.insert_change_record(conn, _make_change("chg_1", symbol, version_to="4.0"))

    candidates = blocking.generate_candidates(conn, symbol, version_to="3.0")

    assert candidates == []
