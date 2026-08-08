from src.extraction.version_normalization import (
    VersionQualifier,
    find_version_mentions,
    parse_version_expression,
)

"""
Test deterministic version-expression parsing: "v1.2", "1.2.x",
"since 1.2", "removed in 2.0", and ranges, normalized into a structured
VersionMention rather than left as free text.
"""


def test_bare_v_prefixed_version():
    mention = parse_version_expression("Removed in v2.0.")

    assert mention.normalized == "2.0"
    assert mention.qualifier == VersionQualifier.EXACT.value


def test_wildcard_patch_version_normalizes_to_minor():
    mention = parse_version_expression("Available starting with 1.2.x.")

    assert mention.normalized == "1.2"


def test_since_qualifier():
    mention = parse_version_expression("Deprecated since 1.2.")

    assert mention.normalized == "1.2"
    assert mention.qualifier == VersionQualifier.SINCE.value


def test_removed_in_keyword_is_exact():
    mention = parse_version_expression("removed in 2.0")

    assert mention.normalized == "2.0"
    assert mention.qualifier == VersionQualifier.EXACT.value


def test_range_with_dash():
    mention = parse_version_expression("Changes in 1.2 - 2.0.")

    assert mention.qualifier == VersionQualifier.RANGE.value
    assert mention.normalized == "1.2"
    assert mention.normalized_end == "2.0"


def test_range_with_to():
    mention = parse_version_expression("Migrate from 1.2 to 2.0.")

    assert mention.qualifier == VersionQualifier.RANGE.value
    assert mention.normalized == "1.2"
    assert mention.normalized_end == "2.0"


def test_range_with_between_and():
    mention = parse_version_expression("Changes between 1.2 and 2.0.")

    assert mention.qualifier == VersionQualifier.RANGE.value
    assert mention.normalized == "1.2"
    assert mention.normalized_end == "2.0"


def test_no_version_mention_returns_none():
    assert parse_version_expression("Python 3 requires 5 minutes.") is None


def test_find_version_mentions_does_not_double_count_range_as_bare():
    mentions = find_version_mentions("Migrate from 1.2 to 2.0.")

    assert len(mentions) == 1
    assert mentions[0].qualifier == VersionQualifier.RANGE.value


def test_find_version_mentions_returns_multiple_independent_mentions():
    mentions = find_version_mentions("Available in 1.2 and again in 3.4.")

    assert [m.normalized for m in mentions] == ["1.2", "3.4"]
