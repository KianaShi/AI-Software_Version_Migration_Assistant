from dataclasses import dataclass

from src.extraction.version_normalization import (
    VersionQualifier,
    parse_version_expression,
)

"""
Version interval overlap, not exact string matching.

A query like "migrating from 1.2 to 2.0" and a chunk tagged version="1.5"
should match even though the strings differ -- 1.5 falls inside [1.2,
2.0]. Both sides get parsed into a VersionInterval and compared with
intervals_overlap(), reusing extraction.version_normalization rather than
re-parsing version syntax here.

This is a scoped, non-strict comparison: parse_version_key() only orders
numeric dot-separated components (1.2 < 1.10 correctly, since it compares
ints not strings) and stops at the first non-numeric segment. No full
semver (pre-release/build metadata) support -- not needed by anything
downstream yet.
"""


@dataclass
class VersionInterval:
    start: tuple[int, ...] | None = None  # None = unbounded below
    end: tuple[int, ...] | None = None    # None = unbounded above


def parse_version_key(normalized: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in normalized.split("."):
        if not token.isdigit():
            break
        parts.append(int(token))
    return tuple(parts) if parts else (0,)


def mention_to_interval(normalized: str, qualifier: str, normalized_end: str | None = None) -> VersionInterval:
    if qualifier == VersionQualifier.RANGE.value:
        return VersionInterval(
            start=parse_version_key(normalized),
            end=parse_version_key(normalized_end) if normalized_end else None,
        )
    if qualifier == VersionQualifier.SINCE.value:
        return VersionInterval(start=parse_version_key(normalized), end=None)
    # EXACT: a single point in version space
    key = parse_version_key(normalized)
    return VersionInterval(start=key, end=key)


def query_version_interval(query_text: str) -> VersionInterval | None:
    mention = parse_version_expression(query_text)
    if mention is None:
        return None
    return mention_to_interval(mention.normalized, mention.qualifier, mention.normalized_end)


def chunk_version_interval(chunk_version: str | None) -> VersionInterval | None:
    if not chunk_version:
        return None
    key = parse_version_key(chunk_version)
    return VersionInterval(start=key, end=key)


def intervals_overlap(a: VersionInterval, b: VersionInterval) -> bool:
    if a.end is not None and b.start is not None and a.end < b.start:
        return False
    if b.end is not None and a.start is not None and b.end < a.start:
        return False
    return True
