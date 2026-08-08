from src.entities.models import SourceType, generate_id
from src.extraction.models import SourceDocument

"""
Source adapters: normalize raw text you already have, plus its metadata,
into a common SourceDocument shape. Each adapter keeps the URL, version,
date, source type, and a human-readable provenance string alongside the
raw text, so every later claim stays traceable back to where it came from.

None of these fetch anything -- pulling from the GitHub API, crawling docs
sites, etc. is separate infrastructure (auth, rate limits) left for later.
"""


def _document_id(source_type: str, url: str | None, raw_text: str) -> str:
    return generate_id("doc", source_type, url or "", raw_text[:200])


def parse_release_note(
    raw_text: str,
    url: str | None = None,
    version: str | None = None,
    date: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        document_id=_document_id(SourceType.RELEASE_NOTE.value, url, raw_text),
        source_type=SourceType.RELEASE_NOTE.value,
        raw_text=raw_text,
        provenance=f"release note{f' ({url})' if url else ''}",
        url=url,
        version=version,
        date=date,
    )


def parse_migration_guide(
    raw_text: str,
    url: str | None = None,
    version: str | None = None,
    date: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        document_id=_document_id(SourceType.MIGRATION_GUIDE.value, url, raw_text),
        source_type=SourceType.MIGRATION_GUIDE.value,
        raw_text=raw_text,
        provenance=f"migration guide{f' ({url})' if url else ''}",
        url=url,
        version=version,
        date=date,
    )


def parse_official_docs(
    raw_text: str,
    url: str | None = None,
    version: str | None = None,
    date: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        document_id=_document_id(SourceType.OFFICIAL_DOCS.value, url, raw_text),
        source_type=SourceType.OFFICIAL_DOCS.value,
        raw_text=raw_text,
        provenance=f"official docs{f' ({url})' if url else ''}",
        url=url,
        version=version,
        date=date,
    )


def parse_github_pr_issue(
    raw_text: str,
    url: str | None = None,
    version: str | None = None,
    date: str | None = None,
    reference: str | None = None,
) -> SourceDocument:
    """
    reference: the PR/issue number (e.g. "PR#4213", "#987"), when known.
    It is not parsed out of raw_text here -- callers who already have it
    from the GitHub API/URL should pass it straight through so it can be
    folded into an UnresolvedChange's external_refs by change_extraction.
    """
    provenance = "github pr/issue"
    if reference:
        provenance += f" {reference}"
    if url:
        provenance += f" ({url})"

    return SourceDocument(
        document_id=_document_id(SourceType.GITHUB_PR_ISSUE.value, url, raw_text),
        source_type=SourceType.GITHUB_PR_ISSUE.value,
        raw_text=raw_text,
        provenance=provenance,
        url=url,
        version=version,
        date=date,
        document_refs=[reference] if reference else [],
    )
