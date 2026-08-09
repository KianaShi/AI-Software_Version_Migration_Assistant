from pathlib import Path

from src.aggregation import linker
from src.entities import store
from src.entities.models import (
    ChangeRecord,
    ConfidenceTier,
    Evidence,
    LinkMethod,
    LinkType,
    ReviewStatus,
    Symbol,
    UnresolvedChange,
)

"""
End-to-end test of Level 2 aggregation: candidate generation -> pairwise
resolution -> cannot-link constraints -> evidence link, orchestrated by
linker.resolve_evidence().
"""

SYMBOL = Symbol(name="requests.Session.verify", package="requests")


def _make_conn():
    conn = store.get_connection(Path(":memory:"))
    store.init_db(conn)
    return conn


def _evidence(evidence_id="ev_1", external_refs=None, symbol_mentions=None):
    return Evidence(
        evidence_id=evidence_id,
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        symbol_mentions=symbol_mentions or [SYMBOL],
        raw_text="the verify parameter was removed",
        external_refs=external_refs if external_refs is not None else [],
    )


def _unresolved(summary="verify parameter removed", version_to="3.0", external_refs=None):
    return UnresolvedChange(
        symbol=SYMBOL,
        version_from="2.0",
        version_to=version_to,
        change_type="REMOVED",
        summary=summary,
        external_refs=external_refs if external_refs is not None else [],
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        raw_text="the verify parameter was removed",
    )


def _existing_change(change_id="chg_existing", summary="verify parameter removed", version_to="3.0", external_refs=None):
    return ChangeRecord(
        symbol=SYMBOL,
        version_from="2.0",
        version_to=version_to,
        change_type="REMOVED",
        summary=summary,
        external_refs=external_refs if external_refs is not None else [],
        change_id=change_id,
        source_type="MIGRATION_GUIDE",
        source_document_id="doc_0",
        raw_text="verify parameter was removed",
    )


def test_originated_change_carries_replacement_symbol_and_parameters():
    conn = _make_conn()
    unresolved = UnresolvedChange(
        symbol=SYMBOL,
        version_from="2.0",
        version_to="3.0",
        change_type="REPLACEMENT",
        summary="verify was replaced by ssl_verify",
        replacement_symbol="requests.Session.ssl_verify",
        parameters=["verify"],
        source_type="RELEASE_NOTE",
        source_document_id="doc_1",
        raw_text="verify was replaced by ssl_verify",
    )

    links = linker.resolve_evidence(conn, _evidence(), unresolved)

    change = store.get_change_record(conn, links[0].change_id)
    assert change.replacement_symbol == "requests.Session.ssl_verify"
    assert change.parameters == ["verify"]


def test_no_candidates_originates_new_change():
    conn = _make_conn()

    links = linker.resolve_evidence(conn, _evidence(), _unresolved())

    assert len(links) == 1
    link = links[0]
    assert link.link_type == LinkType.PRIMARY.value
    assert link.link_method == LinkMethod.ORIGINATING.value
    assert link.confidence_tier == ConfidenceTier.EXPLICIT.value
    assert link.review_status == ReviewStatus.UNREVIEWED.value

    # the new change record must actually be persisted
    assert store.get_change_record(conn, link.change_id) is not None
    assert store.get_links_for_evidence(conn, "ev_1") == links


def test_shared_external_ref_resolves_to_existing_change():
    conn = _make_conn()
    store.insert_change_record(conn, _existing_change(external_refs=["PR#100"]))

    links = linker.resolve_evidence(
        conn, _evidence(external_refs=["PR#100"]), _unresolved(external_refs=["PR#100"])
    )

    assert len(links) == 1
    link = links[0]
    assert link.change_id == "chg_existing"
    assert link.link_type == LinkType.SUPPORTING.value
    assert link.confidence_tier == ConfidenceTier.EXPLICIT.value
    assert link.link_method == LinkMethod.EXPLICIT_REFERENCE.value
    assert link.review_status == ReviewStatus.UNREVIEWED.value


def test_high_confidence_inferred_match_resolves_without_review():
    conn = _make_conn()
    store.insert_change_record(conn, _existing_change())

    links = linker.resolve_evidence(conn, _evidence(), _unresolved())

    assert len(links) == 1
    link = links[0]
    assert link.change_id == "chg_existing"
    assert link.confidence_tier == ConfidenceTier.INFERRED_HIGH_CONFIDENCE.value
    assert link.review_status == ReviewStatus.UNREVIEWED.value


def test_cannot_linked_candidate_does_not_block_new_change_and_is_recorded():
    conn = _make_conn()
    # existing change with a conflicting explicit reference -> hard cannot-link
    store.insert_change_record(conn, _existing_change(external_refs=["PR#999"]))

    links = linker.resolve_evidence(
        conn, _evidence(external_refs=["PR#100"]), _unresolved(external_refs=["PR#100"])
    )

    assert len(links) == 1
    new_change_id = links[0].change_id
    assert new_change_id != "chg_existing"

    constraint = store.get_cannot_link(conn, new_change_id, "chg_existing")
    assert constraint is not None
    assert constraint.reason == "EXPLICIT_DIFFERENT_REFERENCE"


def test_multiple_plausible_candidates_are_never_auto_picked():
    conn = _make_conn()
    store.insert_change_record(conn, _existing_change(change_id="chg_a", summary=""))
    store.insert_change_record(conn, _existing_change(change_id="chg_b", summary=""))

    links = linker.resolve_evidence(conn, _evidence(), _unresolved(summary=""))

    assert len(links) == 2
    change_ids = {link.change_id for link in links}
    assert change_ids == {"chg_a", "chg_b"}
    for link in links:
        assert link.review_status == ReviewStatus.NEEDS_REVIEW.value
