"""
Domain model for the entity/symbol layer.

Two families of dataclasses matter here:

- ``ChangeAttributes`` fields describe *what a change looks like*. Both
  ``UnresolvedChange`` (the not-yet-linked output a future Level 1 extraction
  step must produce from a release note / PR diff / migration guide) and
  ``ChangeRecord`` (a persisted, canonical change with a stable change_id)
  share these fields, so aggregation code can compare them structurally
  without caring which one it received.
- Everything else (``Evidence``, ``EvidenceLink``, ``CannotLinkConstraint``)
  is part of the evidence-aggregation record keeping described in the
  design: change_id is the cross-document foreign key, symbol is only a
  blocking key, and every link records how and why it was made.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


def generate_id(prefix: str, *parts: str) -> str:
    """Deterministic, content-derived id (same inputs -> same id)."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


class SourceType(str, Enum):
    RELEASE_NOTE = "RELEASE_NOTE"
    PR_DIFF = "PR_DIFF"
    MIGRATION_GUIDE = "MIGRATION_GUIDE"


class ChangeType(str, Enum):
    REMOVED = "REMOVED"
    RENAMED = "RENAMED"
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"
    DEPRECATED = "DEPRECATED"
    BEHAVIOR_CHANGED = "BEHAVIOR_CHANGED"
    MOVED = "MOVED"


class LinkType(str, Enum):
    PRIMARY = "PRIMARY"           # evidence that originated this change_id
    SUPPORTING = "SUPPORTING"     # evidence resolved onto an existing change_id
    CROSS_REFERENCE = "CROSS_REFERENCE"  # evidence that only points at the change


class LinkMethod(str, Enum):
    ORIGINATING = "ORIGINATING"              # this evidence created the change_id
    EXPLICIT_REFERENCE = "EXPLICIT_REFERENCE"  # shared PR#/commit sha/etc.
    PAIRWISE_RESOLUTION = "PAIRWISE_RESOLUTION"  # scored structural+semantic match
    MANUAL_REVIEW = "MANUAL_REVIEW"            # a human confirmed/rejected it


class ConfidenceTier(str, Enum):
    EXPLICIT = "EXPLICIT"
    INFERRED_HIGH_CONFIDENCE = "INFERRED_HIGH_CONFIDENCE"
    AMBIGUOUS = "AMBIGUOUS"


class ReviewStatus(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class CannotLinkReason(str, Enum):
    INCOMPATIBLE_VERSION_TRANSITION = "INCOMPATIBLE_VERSION_TRANSITION"
    NON_OVERLAPPING_SEMANTICS = "NON_OVERLAPPING_SEMANTICS"
    SEPARATE_RELEASE_EVENTS = "SEPARATE_RELEASE_EVENTS"
    EXPLICIT_DIFFERENT_REFERENCE = "EXPLICIT_DIFFERENT_REFERENCE"


class PairwiseDecision(str, Enum):
    MATCH_EXPLICIT = "MATCH_EXPLICIT"
    MATCH_INFERRED = "MATCH_INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True)
class Symbol:
    name: str
    package: str
    kind: str | None = None


@dataclass
class ChangeAttributes:
    """Fields shared by an unresolved (Level 1 output) and a persisted change."""

    symbol: Symbol
    version_from: str | None
    version_to: str | None
    change_type: str  # ChangeType value
    summary: str
    external_refs: list[str] = field(default_factory=list)


@dataclass
class UnresolvedChange(ChangeAttributes):
    """
    The contract a future Level 1 extraction step must satisfy: everything
    needed to attempt resolution against the existing change registry, but
    with no change_id yet since identity hasn't been decided.
    """

    source_type: str = ""  # SourceType value
    source_document_id: str = ""
    raw_text: str = ""


@dataclass
class ChangeRecord(ChangeAttributes):
    """A canonical, persisted change. change_id is the cross-document FK."""

    change_id: str = ""
    source_type: str = ""  # SourceType value
    source_document_id: str = ""
    raw_text: str = ""


@dataclass
class Evidence:
    evidence_id: str
    source_type: str  # SourceType value
    source_document_id: str
    symbol_mentions: list[Symbol]
    raw_text: str
    external_refs: list[str] = field(default_factory=list)
    embedding_id: str | None = None


@dataclass
class CannotLinkConstraint:
    change_id_a: str
    change_id_b: str
    reason: str  # CannotLinkReason value
    provenance: str
    created_by: str = "system"


@dataclass
class EvidenceLink:
    evidence_id: str
    change_id: str
    link_type: str          # LinkType value
    link_confidence: float  # internal only; never shown raw to end users
    confidence_tier: str    # ConfidenceTier value, derived from link_confidence
    link_method: str        # LinkMethod value
    provenance: str
    review_status: str = ReviewStatus.UNREVIEWED.value
