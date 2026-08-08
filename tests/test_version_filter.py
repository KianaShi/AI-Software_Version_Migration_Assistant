from src.retrieval.version_filter import (
    VersionInterval,
    chunk_version_interval,
    intervals_overlap,
    parse_version_key,
    query_version_interval,
)

"""
Test version interval overlap -- retrieval must match on overlap, not
exact string equality, so "migrate from 1.2 to 2.0" matches a chunk
tagged "1.5" even though the strings differ.
"""


def test_parse_version_key_orders_numerically_not_lexically():
    assert parse_version_key("1.2") < parse_version_key("1.10")


def test_parse_version_key_stops_at_non_numeric_segment():
    assert parse_version_key("1.2.x") == (1, 2)


def test_query_range_overlaps_point_inside_it():
    query = query_version_interval("Migrate from 1.2 to 2.0.")
    chunk = chunk_version_interval("1.5")

    assert intervals_overlap(query, chunk) is True


def test_query_range_does_not_overlap_point_outside_it():
    query = query_version_interval("Migrate from 1.2 to 2.0.")
    chunk = chunk_version_interval("2.5")

    assert intervals_overlap(query, chunk) is False


def test_range_boundary_is_inclusive():
    query = query_version_interval("Migrate from 1.2 to 2.0.")

    assert intervals_overlap(query, chunk_version_interval("1.2")) is True
    assert intervals_overlap(query, chunk_version_interval("2.0")) is True


def test_since_qualifier_is_unbounded_above():
    query = query_version_interval("Deprecated since 1.2.")

    assert intervals_overlap(query, chunk_version_interval("99.0")) is True
    assert intervals_overlap(query, chunk_version_interval("1.0")) is False


def test_unbounded_interval_overlaps_everything():
    unbounded = VersionInterval()

    assert intervals_overlap(unbounded, chunk_version_interval("1.0")) is True
    assert intervals_overlap(unbounded, chunk_version_interval("99.9")) is True


def test_no_version_mention_in_query_returns_none():
    assert query_version_interval("How do I use this library?") is None


def test_no_version_on_chunk_returns_none():
    assert chunk_version_interval(None) is None
    assert chunk_version_interval("") is None
