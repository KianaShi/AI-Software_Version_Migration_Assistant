from src.entities.models import ConfidenceTier, EvidenceLink, ReviewStatus

"""
User-facing text for evidence links.

Every user-facing surface must go through describe_link()/describe_review_status()
rather than reading link_confidence or confidence_tier directly -- raw
confidence numbers are an internal calibration detail, not something a
migration-assistant user should have to interpret.
"""

_TIER_LABELS = {
    ConfidenceTier.EXPLICIT.value: "Confirmed by explicit reference",
    ConfidenceTier.INFERRED_HIGH_CONFIDENCE.value: "Likely the same change",
    ConfidenceTier.AMBIGUOUS.value: "Possibly related — needs review",
}

_REVIEW_STATUS_LABELS = {
    ReviewStatus.UNREVIEWED.value: "",
    ReviewStatus.NEEDS_REVIEW.value: "needs human review before use",
    ReviewStatus.CONFIRMED.value: "confirmed by a reviewer",
    ReviewStatus.REJECTED.value: "rejected by a reviewer",
}


def describe_link(link: EvidenceLink) -> str:
    tier_label = _TIER_LABELS[link.confidence_tier]
    status_label = _REVIEW_STATUS_LABELS[link.review_status]
    return f"{tier_label} ({status_label})" if status_label else tier_label
