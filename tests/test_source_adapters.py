from src.entities.models import SourceType
from src.extraction.sources import (
    parse_github_pr_issue,
    parse_migration_guide,
    parse_official_docs,
    parse_release_note,
)

"""
Test source adapters.

Each adapter normalizes raw text plus metadata into a SourceDocument that
carries source_type, url, version, date, and a human-readable provenance
string -- no network access happens here.
"""


def test_parse_release_note_carries_metadata():
    doc = parse_release_note(
        "Removed the verify parameter.",
        url="https://example.com/release/5.0",
        version="5.0",
        date="2026-01-01",
    )

    assert doc.source_type == SourceType.RELEASE_NOTE.value
    assert doc.url == "https://example.com/release/5.0"
    assert doc.version == "5.0"
    assert doc.date == "2026-01-01"
    assert "release note" in doc.provenance
    assert doc.raw_text == "Removed the verify parameter."


def test_parse_migration_guide_sets_source_type():
    doc = parse_migration_guide("Migrate from v1 to v2.")

    assert doc.source_type == SourceType.MIGRATION_GUIDE.value
    assert "migration guide" in doc.provenance


def test_parse_official_docs_sets_source_type():
    doc = parse_official_docs("API reference.")

    assert doc.source_type == SourceType.OFFICIAL_DOCS.value
    assert "official docs" in doc.provenance


def test_parse_github_pr_issue_carries_reference_as_document_ref():
    doc = parse_github_pr_issue(
        "This PR removes the verify parameter.",
        url="https://github.com/org/repo/pull/4213",
        reference="PR#4213",
    )

    assert doc.source_type == SourceType.GITHUB_PR_ISSUE.value
    assert doc.document_refs == ["PR#4213"]
    assert "PR#4213" in doc.provenance


def test_parse_github_pr_issue_without_reference_has_no_document_refs():
    doc = parse_github_pr_issue("An issue thread.")

    assert doc.document_refs == []


def test_document_id_is_stable_for_same_input():
    doc_a = parse_release_note("Same text.", url="https://example.com")
    doc_b = parse_release_note("Same text.", url="https://example.com")

    assert doc_a.document_id == doc_b.document_id


def test_document_id_differs_for_different_text():
    doc_a = parse_release_note("Text A.")
    doc_b = parse_release_note("Text B.")

    assert doc_a.document_id != doc_b.document_id
