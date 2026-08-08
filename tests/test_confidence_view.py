from src.entities.models import ConfidenceTier, EvidenceLink, ReviewStatus
from src.presentation.confidence_view import describe_link

"""
Test the presentation layer's confidence descriptions.

The whole point of this layer is that no raw confidence number or internal
tier/status enum value ever reaches user-facing text -- only fixed labels.
"""


def _link(confidence_tier, review_status, link_confidence=0.9123456):
    return EvidenceLink(
        evidence_id="ev_1",
        change_id="chg_1",
        link_type="SUPPORTING",
        link_confidence=link_confidence,
        confidence_tier=confidence_tier,
        link_method="PAIRWISE_RESOLUTION",
        provenance="test",
        review_status=review_status,
    )


def test_describe_link_never_leaks_raw_confidence_number():
    link = _link(ConfidenceTier.INFERRED_HIGH_CONFIDENCE.value, ReviewStatus.UNREVIEWED.value)

    description = describe_link(link)

    assert "0.9" not in description
    assert str(link.link_confidence) not in description


def test_describe_link_covers_all_tiers():
    for tier in ConfidenceTier:
        description = describe_link(_link(tier.value, ReviewStatus.UNREVIEWED.value))
        assert description  # non-empty label for every tier


def test_describe_link_flags_needs_review():
    link = _link(ConfidenceTier.AMBIGUOUS.value, ReviewStatus.NEEDS_REVIEW.value)

    assert "review" in describe_link(link).lower()
