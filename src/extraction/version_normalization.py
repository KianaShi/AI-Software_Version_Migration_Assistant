import re
from dataclasses import dataclass
from enum import Enum

"""
Deterministic version-expression parsing.

Turns free-text version mentions ("v1.2", "1.2.x", "since 1.2", "removed
in 2.0", "1.2 to 2.0") into a structured VersionMention. This only
normalizes syntax (drop "v" prefix, drop ".x" wildcard suffix) -- it does
not attempt full semver comparison/ordering, which downstream aggregation
code doesn't currently need (constraints.py compares version strings for
equality, not ordering).

VersionPrecision (Stage 8A) records how specific the SOURCE text actually
was -- "v2" is a MAJOR-precision claim, "v2.0" MINOR, "v2.0.0" PATCH --
without manufacturing precision the source didn't state. This is
deliberately the smallest useful representation, not a full SemVer
interval engine: no ordering/comparison operators are defined over it,
and intervals_overlap() in retrieval/version_filter.py is intentionally
left unchanged (it already pads mismatched-length version-key tuples for
comparison purposes, which is a different concern from what precision a
claim asserts). Full semantic-interval representation, prerelease
ordering, and wildcard ranges are explicitly out of scope here -- see
docs/entity-aggregation-log.md Stage 8A for the reasoning.
"""


class VersionQualifier(str, Enum):
    EXACT = "EXACT"    # "v1.2", "version 2.0", "removed in 2.0"
    SINCE = "SINCE"     # "since 1.2", "as of 1.2", "introduced in 1.2"
    RANGE = "RANGE"      # "1.2 to 2.0", "1.2 - 2.0"


class VersionPrecision(str, Enum):
    MAJOR = "MAJOR"  # "v2" -- only one component stated
    MINOR = "MINOR"  # "v2.0" -- two components stated
    PATCH = "PATCH"  # "v2.0.0" -- three or more components stated


def _precision_of(normalized_token: str) -> str:
    """
    Component count of the NORMALIZED token (after ".x" wildcard
    stripping, so "1.2.x" -- MINOR precision, the "x" isn't a real patch
    number -- not PATCH).
    """
    parts = normalized_token.split(".")
    if len(parts) <= 1:
        return VersionPrecision.MAJOR.value
    if len(parts) == 2:
        return VersionPrecision.MINOR.value
    return VersionPrecision.PATCH.value


@dataclass
class VersionMention:
    raw: str
    normalized: str | None  # None if the matched text couldn't be normalized
    qualifier: str  # VersionQualifier value
    span: tuple[int, int]
    normalized_end: str | None = None  # only set for RANGE
    precision: str | None = None  # VersionPrecision value, derived from `normalized`


_VERSION_NUM = r"\d+(?:\.\d+)*(?:\.[xX])?"
# a dot is required for the "v"-less bare fallback, so plain prose numbers
# ("Python 3", "5 minutes") don't get misread as versions
_VERSION_NUM_DOTTED = r"\d+\.\d+(?:\.\d+)*(?:\.[xX])?"

_RANGE_RE = re.compile(
    rf"\bv?({_VERSION_NUM})\s*(?:-|–|—|to)\s*v?({_VERSION_NUM})\b"
)
_BETWEEN_RANGE_RE = re.compile(
    rf"\bbetween\s+v?({_VERSION_NUM})\s+and\s+v?({_VERSION_NUM})\b", re.IGNORECASE
)
_SINCE_RE = re.compile(
    rf"\b(?:since|as of|starting (?:in|from)|introduced in)\s+v?({_VERSION_NUM})\b",
    re.IGNORECASE,
)
_EXACT_KEYWORD_RE = re.compile(
    rf"\b(?:removed in|deprecated in|changed in|in version|version)\s+v?({_VERSION_NUM})\b",
    re.IGNORECASE,
)
_BARE_VERSION_RE = re.compile(rf"\bv({_VERSION_NUM})\b")
_BARE_DOTTED_RE = re.compile(rf"\b({_VERSION_NUM_DOTTED})\b")


def _normalize_token(token: str) -> str:
    return re.sub(r"\.[xX]$", "", token)


def find_version_mentions(text: str) -> list[VersionMention]:
    """
    Find all version mentions in text, most-specific pattern first so a
    range or "since X" phrase isn't also double-counted as a bare version.
    """
    mentions: list[VersionMention] = []
    claimed: list[tuple[int, int]] = []

    def _overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < end and start < span[1] for start, end in claimed)

    for pattern in (_BETWEEN_RANGE_RE, _RANGE_RE):
        for match in pattern.finditer(text):
            span = match.span()
            if _overlaps(span):
                continue
            normalized = _normalize_token(match.group(1))
            mentions.append(
                VersionMention(
                    raw=match.group(0),
                    normalized=normalized,
                    normalized_end=_normalize_token(match.group(2)),
                    qualifier=VersionQualifier.RANGE.value,
                    span=span,
                    precision=_precision_of(normalized),
                )
            )
            claimed.append(span)

    for pattern, qualifier in (
        (_SINCE_RE, VersionQualifier.SINCE),
        (_EXACT_KEYWORD_RE, VersionQualifier.EXACT),
    ):
        for match in pattern.finditer(text):
            span = match.span()
            if _overlaps(span):
                continue
            normalized = _normalize_token(match.group(1))
            mentions.append(
                VersionMention(
                    raw=match.group(0),
                    normalized=normalized,
                    qualifier=qualifier.value,
                    span=span,
                    precision=_precision_of(normalized),
                )
            )
            claimed.append(span)

    for pattern in (_BARE_VERSION_RE, _BARE_DOTTED_RE):
        for match in pattern.finditer(text):
            span = match.span()
            if _overlaps(span):
                continue
            normalized = _normalize_token(match.group(1))
            mentions.append(
                VersionMention(
                    raw=match.group(0),
                    normalized=normalized,
                    qualifier=VersionQualifier.EXACT.value,
                    span=span,
                    precision=_precision_of(normalized),
                )
            )
            claimed.append(span)

    mentions.sort(key=lambda m: m.span[0])
    return mentions


def parse_version_expression(text: str) -> VersionMention | None:
    """Convenience wrapper: the first (leftmost) version mention in text, if any."""
    mentions = find_version_mentions(text)
    return mentions[0] if mentions else None
