from src.extraction.sources import parse_github_pr_issue, parse_migration_guide, parse_release_note
from src.retrieval.chunking import chunk_document

"""
Test source-aware chunking: release notes chunk per bullet entry within
each version-heading section, migration guides chunk per heading section,
and PR/issue bodies chunk per paragraph.
"""


def test_release_note_chunks_per_bullet_with_ambient_version():
    text = "## v5.0.0\n- `FooClient.create()` was removed.\n- `BarClient.build()` was renamed.\n"
    doc = parse_release_note(text)

    chunks = chunk_document(doc, default_package="foo")

    assert len(chunks) == 2
    assert all(c.version == "5.0.0" for c in chunks)
    assert chunks[0].text == "`FooClient.create()` was removed."
    assert chunks[0].symbols == ["FooClient.create"]


def test_release_note_separates_entries_across_version_sections():
    text = "## v5.0.0\n- Entry A.\n\n## v3.0.0\n- Entry B.\n"
    doc = parse_release_note(text)

    chunks = chunk_document(doc, default_package="foo")

    versions = {c.text: c.version for c in chunks}
    assert versions["Entry A."] == "5.0.0"
    assert versions["Entry B."] == "3.0.0"


def test_migration_guide_chunks_per_heading_section():
    text = "# Guide\nIntro.\n\n## Step 1\nDo the thing.\n\n## Step 2\nDo another thing.\n"
    doc = parse_migration_guide(text)

    chunks = chunk_document(doc, default_package="foo")

    texts = [c.text for c in chunks]
    assert "Intro." in texts
    assert "Do the thing." in texts
    assert "Do another thing." in texts


def test_github_pr_issue_chunks_per_paragraph():
    text = "First paragraph.\n\nSecond paragraph about `FooClient.create()`."
    doc = parse_github_pr_issue(text)

    chunks = chunk_document(doc, default_package="foo")

    assert len(chunks) == 2
    assert chunks[1].symbols == ["FooClient.create"]


def test_chunk_source_document_id_traces_back_to_document():
    doc = parse_release_note("## v1.0\n- Entry.\n")

    chunks = chunk_document(doc)

    assert all(c.source_document_id == doc.document_id for c in chunks)


def test_chunk_evidence_id_hook_defaults_to_none():
    doc = parse_release_note("## v1.0\n- Entry.\n")

    chunks = chunk_document(doc)

    assert all(c.evidence_id is None for c in chunks)


def test_inline_version_overrides_missing_ambient_version():
    doc = parse_migration_guide("Some intro with no heading, removed in 2.0.")

    chunks = chunk_document(doc)

    assert chunks[0].version == "2.0"
