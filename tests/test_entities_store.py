from pathlib import Path

from src.entities import store
from src.entities.models import (
    CannotLinkConstraint,
    ChangeRecord,
    Evidence,
    EvidenceLink,
    Symbol,
)

"""
Test the SQLite-backed entity/symbol store.

This verifies the store can:
- Create tables
- Insert and fetch change records, evidence, evidence links, and
  cannot-link constraints
- Find candidate change records by the symbol blocking key
"""


def _make_conn():
    conn = store.get_connection(Path(":memory:"))
    store.init_db(conn)
    return conn


def _make_change(change_id="chg_1", version_to="3.0"):
    return ChangeRecord(
        symbol=Symbol(name="requests.Session.verify", package="requests"),
        version_from="2.0",
        version_to=version_to,
        change_type="REMOVED",
        summary="verify parameter removed",
        external_refs=["PR#100"],
        change_id=change_id,
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        raw_text="removed verify param",
    )


def test_insert_and_get_change_record():
    conn = _make_conn()
    change = _make_change()

    store.insert_change_record(conn, change)
    fetched = store.get_change_record(conn, "chg_1")

    assert fetched == change


def test_get_change_record_missing_returns_none():
    conn = _make_conn()

    assert store.get_change_record(conn, "does_not_exist") is None


def test_find_candidates_by_symbol_matches_name_and_package():
    conn = _make_conn()
    change = _make_change()
    store.insert_change_record(conn, change)

    other_package = _make_change(change_id="chg_2")
    other_package.symbol = Symbol(name="requests.Session.verify", package="other_pkg")
    store.insert_change_record(conn, other_package)

    candidates = store.find_candidates_by_symbol(
        conn, Symbol(name="requests.Session.verify", package="requests")
    )

    assert [c.change_id for c in candidates] == ["chg_1"]


def test_find_candidates_by_symbol_filters_known_different_version():
    conn = _make_conn()
    store.insert_change_record(conn, _make_change(change_id="chg_1", version_to="3.0"))
    store.insert_change_record(conn, _make_change(change_id="chg_2", version_to="4.0"))
    store.insert_change_record(conn, _make_change(change_id="chg_3", version_to=None))

    candidates = store.find_candidates_by_symbol(
        conn,
        Symbol(name="requests.Session.verify", package="requests"),
        version_to="3.0",
    )

    ids = {c.change_id for c in candidates}
    assert ids == {"chg_1", "chg_3"}


def test_insert_and_get_evidence():
    conn = _make_conn()
    evidence = Evidence(
        evidence_id="ev_1",
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        symbol_mentions=[Symbol(name="requests.Session.verify", package="requests")],
        raw_text="the verify parameter was removed",
        external_refs=["PR#100"],
        embedding_id="chunk_0",
    )

    store.insert_evidence(conn, evidence)
    fetched = store.get_evidence(conn, "ev_1")

    assert fetched == evidence


def test_insert_evidence_link_and_query_both_directions():
    conn = _make_conn()
    store.insert_change_record(conn, _make_change())
    store.insert_evidence(
        conn,
        Evidence(
            evidence_id="ev_1",
            source_type="RELEASE_NOTE",
            source_document_id="doc_1",
            symbol_mentions=[],
            raw_text="text",
        ),
    )

    link = EvidenceLink(
        evidence_id="ev_1",
        change_id="chg_1",
        link_type="PRIMARY",
        link_confidence=1.0,
        confidence_tier="EXPLICIT",
        link_method="ORIGINATING",
        provenance="test",
        review_status="UNREVIEWED",
    )
    store.insert_evidence_link(conn, link)

    assert store.get_links_for_change(conn, "chg_1") == [link]
    assert store.get_links_for_evidence(conn, "ev_1") == [link]


def test_cannot_link_constraint_is_order_independent():
    conn = _make_conn()
    constraint = CannotLinkConstraint(
        change_id_a="chg_2",
        change_id_b="chg_1",
        reason="EXPLICIT_DIFFERENT_REFERENCE",
        provenance="disjoint refs",
    )

    store.insert_cannot_link(conn, constraint)

    assert store.get_cannot_link(conn, "chg_1", "chg_2") is not None
    assert store.get_cannot_link(conn, "chg_2", "chg_1") is not None


def test_get_cannot_link_missing_returns_none():
    conn = _make_conn()

    assert store.get_cannot_link(conn, "chg_1", "chg_2") is None
