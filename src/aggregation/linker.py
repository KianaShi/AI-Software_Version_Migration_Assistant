import sqlite3

from src.aggregation import blocking, pairwise
from src.entities import store
from src.entities.models import (
    CannotLinkConstraint,
    ChangeRecord,
    ConfidenceTier,
    Evidence,
    EvidenceLink,
    LinkMethod,
    LinkType,
    PairwiseDecision,
    ReviewStatus,
    UnresolvedChange,
    generate_id,
)

"""
Level 2 aggregation orchestrator: candidate generation -> pairwise change
resolution -> hard cannot-link constraints -> evidence link.

This intentionally is NOT hierarchical/agglomerative clustering over all
evidence at once -- that would risk transitive merges (A~B, B~C therefore
A~C) even when A and C individually shouldn't link. Instead each evidence
item is resolved, one at a time, against the existing change_id registry:
- exactly one confident candidate -> link to it
- no candidate survives cannot-link and scoring -> this evidence originates
  a new change_id
- more than one plausible candidate (conflicting explicit refs, or any mix
  of MATCH_INFERRED/AMBIGUOUS decisions) -> never auto-pick; every plausible
  candidate gets an AMBIGUOUS/NEEDS_REVIEW link instead

This is the precision-first choice: false splits (two change_ids that
should have been one) are recoverable by a reviewer; false merges (one
change_id wrongly absorbing two unrelated changes) silently corrupt
downstream migration instructions.
"""

_DECISION_TO_TIER = {
    PairwiseDecision.MATCH_EXPLICIT.value: ConfidenceTier.EXPLICIT.value,
    PairwiseDecision.MATCH_INFERRED.value: ConfidenceTier.INFERRED_HIGH_CONFIDENCE.value,
    PairwiseDecision.AMBIGUOUS.value: ConfidenceTier.AMBIGUOUS.value,
}


def _make_link(
    evidence: Evidence,
    candidate: ChangeRecord,
    result: pairwise.PairwiseResult,
    review_status: str,
) -> EvidenceLink:
    return EvidenceLink(
        evidence_id=evidence.evidence_id,
        change_id=candidate.change_id,
        link_type=LinkType.SUPPORTING.value,
        link_confidence=result.score.total,
        confidence_tier=_DECISION_TO_TIER[result.decision],
        link_method=result.method,
        provenance=result.rationale,
        review_status=review_status,
    )


def _persist_ruled_out_constraints(
    conn: sqlite3.Connection,
    resolved_change_id: str,
    results: list[tuple[ChangeRecord, pairwise.PairwiseResult]],
) -> None:
    """
    Once this evidence's identity is settled on resolved_change_id, record
    *why* every cannot-linked candidate was excluded, for audit/debugging
    of false splits later.
    """
    for candidate, result in results:
        if candidate.change_id == resolved_change_id:
            continue
        if result.constraint.allowed:
            continue

        store.insert_cannot_link(
            conn,
            CannotLinkConstraint(
                change_id_a=resolved_change_id,
                change_id_b=candidate.change_id,
                reason=result.constraint.reason or "",
                provenance=result.constraint.detail or result.rationale,
                created_by="system",
            ),
        )


def resolve_evidence(
    conn: sqlite3.Connection,
    evidence: Evidence,
    unresolved: UnresolvedChange,
) -> list[EvidenceLink]:
    if store.get_evidence(conn, evidence.evidence_id) is None:
        store.insert_evidence(conn, evidence)

    candidates = blocking.generate_candidates(
        conn, unresolved.symbol, version_to=unresolved.version_to
    )
    results = [(candidate, pairwise.resolve(unresolved, candidate)) for candidate in candidates]

    confident_matches = [
        (c, r)
        for c, r in results
        if r.decision in (PairwiseDecision.MATCH_EXPLICIT.value, PairwiseDecision.MATCH_INFERRED.value)
    ]
    ambiguous_matches = [
        (c, r) for c, r in results if r.decision == PairwiseDecision.AMBIGUOUS.value
    ]

    links: list[EvidenceLink] = []
    resolved_change_id: str | None = None

    if len(confident_matches) == 1 and not ambiguous_matches:
        candidate, result = confident_matches[0]
        links.append(_make_link(evidence, candidate, result, ReviewStatus.UNREVIEWED.value))
        resolved_change_id = candidate.change_id

    elif confident_matches or ambiguous_matches:
        # multiple plausible candidates, or a mix of confident + ambiguous:
        # precision-first means we never auto-pick one.
        for candidate, result in confident_matches + ambiguous_matches:
            links.append(_make_link(evidence, candidate, result, ReviewStatus.NEEDS_REVIEW.value))

    else:
        new_change = ChangeRecord(
            symbol=unresolved.symbol,
            version_from=unresolved.version_from,
            version_to=unresolved.version_to,
            change_type=unresolved.change_type,
            summary=unresolved.summary,
            external_refs=unresolved.external_refs,
            replacement_symbol=unresolved.replacement_symbol,
            parameters=unresolved.parameters,
            change_id=generate_id(
                "chg",
                unresolved.symbol.name,
                unresolved.symbol.package,
                unresolved.version_to or "",
                unresolved.change_type,
                evidence.evidence_id,
            ),
            source_type=unresolved.source_type,
            source_document_id=unresolved.source_document_id,
            raw_text=unresolved.raw_text,
        )
        store.insert_change_record(conn, new_change)
        links.append(
            EvidenceLink(
                evidence_id=evidence.evidence_id,
                change_id=new_change.change_id,
                link_type=LinkType.PRIMARY.value,
                link_confidence=1.0,
                confidence_tier=ConfidenceTier.EXPLICIT.value,
                link_method=LinkMethod.ORIGINATING.value,
                provenance="no matching candidate found; evidence originates this change",
                review_status=ReviewStatus.UNREVIEWED.value,
            )
        )
        resolved_change_id = new_change.change_id

    for link in links:
        store.insert_evidence_link(conn, link)

    if resolved_change_id is not None:
        _persist_ruled_out_constraints(conn, resolved_change_id, results)

    return links
