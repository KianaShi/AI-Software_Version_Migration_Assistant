from dataclasses import dataclass, field
from enum import Enum

"""
Level 1 extraction types.

These are deliberately separate from src.entities.models: Level 1 answers
"what does this piece of evidence claim?", never "which existing
ChangeRecord does this belong to?" -- that question belongs to the
aggregation pipeline (blocking/constraints/pairwise/linker), which already
exists and is untouched by anything in this package.
"""


class ExtractionConfidence(str, Enum):
    EXPLICIT = "EXPLICIT"    # change-type, symbol, and version all stated in the same statement
    INFERRED = "INFERRED"    # some part relied on ambient context (e.g. a parent heading) or a heuristic


@dataclass
class SourceDocument:
    """
    The normalized shape every source adapter produces, regardless of
    where the raw text came from. Adapters do not fetch anything over the
    network in this pass -- they normalize text you already have plus its
    metadata into this common shape.
    """

    document_id: str
    source_type: str  # src.entities.models.SourceType value
    raw_text: str
    provenance: str
    url: str | None = None
    version: str | None = None  # ambient/document-level version context, if known
    date: str | None = None     # ISO date string, if known
    # refs the document itself is known to be (e.g. its own PR number),
    # as opposed to refs merely mentioned inline within raw_text
    document_refs: list[str] = field(default_factory=list)
