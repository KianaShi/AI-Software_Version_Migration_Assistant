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
    MIGRATION_GUIDE = "MIGRATION_GUIDE"
    OFFICIAL_DOCS = "OFFICIAL_DOCS"
    GITHUB_PR_ISSUE = "GITHUB_PR_ISSUE"


class ChangeType(str, Enum):
    REMOVED = "REMOVED"
    RENAMED = "RENAMED"
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"
    DEPRECATED = "DEPRECATED"
    BEHAVIOR_CHANGED = "BEHAVIOR_CHANGED"
    MOVED = "MOVED"
    REPLACEMENT = "REPLACEMENT"


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
    # populated for ChangeType.REPLACEMENT: the symbol name this was replaced by
    replacement_symbol: str | None = None
    # parameter names the change specifically implicates, if any (e.g. a
    # SIGNATURE_CHANGED naming exactly which parameter was affected)
    parameters: list[str] = field(default_factory=list)
    # free-text recommended action when it isn't a clean 1:1 symbol swap
    # (e.g. "use dicts instead", "use Annotated with Field constraints
    # instead") -- replacement_symbol is for symbol->symbol renames only;
    # not every migration is one (Stage 8A.1)
    migration_action_text: str | None = None


@dataclass
class UnresolvedChange(ChangeAttributes):
    """
    The contract a future Level 1 extraction step must satisfy: everything
    needed to attempt resolution against the existing change registry, but
    with no change_id yet since identity hasn't been decided.

    Level 1 extraction answers "what does this evidence claim?" only -- it
    must never decide "which existing ChangeRecord is this?" (that's the
    aggregation pipeline's job). extraction_confidence/extraction_method
    describe how *this claim* was derived, not how confidently it matches
    anything else.
    """

    source_type: str = ""  # SourceType value
    source_document_id: str = ""
    raw_text: str = ""
    extraction_confidence: str = ""  # extraction.models.ExtractionConfidence value
    extraction_method: str = ""      # e.g. "regex:version_marker", "llm:structured_fallback"


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
