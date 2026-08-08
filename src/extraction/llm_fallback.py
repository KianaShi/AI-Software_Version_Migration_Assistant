from typing import Protocol

from src.entities.models import UnresolvedChange
from src.extraction.models import SourceDocument

"""
The seam for a structured-LLM extraction fallback.

change_extraction.py is deterministic-first: regex/keyword rules handle
explicit version numbers, PR/symbol references, and a fixed vocabulary of
change verbs. Only statements that clearly *sound* change-relevant (an
ambiguous signal word is present, e.g. "breaking"/"note"/"changed") but
that the deterministic rules can't confidently classify get routed here.

No LLM is wired into this repo yet (see README: "OpenAI API (planned)").
LLMExtractor is the interface a future implementation must satisfy;
NotConfiguredLLMExtractor is the default and simply declines every
statement, so the pipeline runs end-to-end today without a live API call.
"""


class LLMExtractor(Protocol):
    def extract(
        self, statement: str, document: SourceDocument
    ) -> list[UnresolvedChange]:
        """
        Return zero or more UnresolvedChange claims found in `statement`.
        Implementations must still answer only "what does this claim?" --
        never assign a change_id or compare against existing ChangeRecords.
        """
        ...


class NotConfiguredLLMExtractor:
    """Default fallback: declines everything rather than guessing."""

    def extract(
        self, statement: str, document: SourceDocument
    ) -> list[UnresolvedChange]:
        return []
