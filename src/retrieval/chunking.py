import re

from src.entities.models import generate_id
from src.extraction.models import SourceDocument
from src.extraction.symbol_normalization import find_symbol_mentions
from src.extraction.version_normalization import find_version_mentions
from src.retrieval.models import Chunk

"""
Source-aware chunking (baseline, not Late Chunking).

Each source type gets the chunk granularity that matches how it's
actually structured:
- migration_guide / official_docs: heading-scoped sections (prose-heavy,
  one section is usually one coherent topic)
- release_note: version-heading-scoped, then split further into
  individual bullet entries (changelogs are itemized; one bullet is
  usually one change)
- github_pr_issue: paragraph-scoped (PR/issue bodies are rarely
  headed/itemized); "relevant discussion" beyond the body itself isn't
  available without a real GitHub API integration, which is out of scope
  here (see sources.py)
"""

_HEADING_RE = re.compile(r"^#{1,6}\s*(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)


def _heading_sections(text: str) -> list[tuple[str | None, str]]:
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    if headings[0].start() > 0 and text[: headings[0].start()].strip():
        sections.append((None, text[: headings[0].start()]))

    for i, match in enumerate(headings):
        body_start = match.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        version_mentions = find_version_mentions(match.group(1))
        ambient_version = version_mentions[0].normalized if version_mentions else None
        sections.append((ambient_version, text[body_start:body_end]))

    return sections


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _chunk_version(chunk_text: str, ambient_version: str | None, document_version: str | None) -> str | None:
    inline = find_version_mentions(chunk_text)
    if inline:
        return inline[0].normalized
    return ambient_version or document_version


def _make_chunk(
    text: str,
    index: int,
    document: SourceDocument,
    ambient_version: str | None,
    default_package: str | None,
) -> Chunk:
    return Chunk(
        chunk_id=generate_id("chunk", document.document_id, str(index), text[:100]),
        text=text,
        source_document_id=document.document_id,
        source_type=document.source_type,
        provenance=document.provenance,
        package=default_package,
        version=_chunk_version(text, ambient_version, document.version),
        symbols=sorted({m.symbol.name for m in find_symbol_mentions(text, default_package)}),
    )


def _chunk_heading_aware(document: SourceDocument, default_package: str | None) -> list[Chunk]:
    chunks = []
    index = 0
    for ambient_version, body in _heading_sections(document.raw_text):
        if not body.strip():
            continue
        chunks.append(_make_chunk(body.strip(), index, document, ambient_version, default_package))
        index += 1
    return chunks


def _chunk_release_note(document: SourceDocument, default_package: str | None) -> list[Chunk]:
    chunks = []
    index = 0
    for ambient_version, body in _heading_sections(document.raw_text):
        bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
        entries = bullets if bullets else ([body.strip()] if body.strip() else [])
        for entry in entries:
            chunks.append(_make_chunk(entry, index, document, ambient_version, default_package))
            index += 1
    return chunks


def _chunk_paragraphs(document: SourceDocument, default_package: str | None) -> list[Chunk]:
    chunks = []
    for index, paragraph in enumerate(_split_paragraphs(document.raw_text)):
        chunks.append(_make_chunk(paragraph, index, document, None, default_package))
    return chunks


_STRATEGY_BY_SOURCE_TYPE = {
    "RELEASE_NOTE": _chunk_release_note,
    "MIGRATION_GUIDE": _chunk_heading_aware,
    "OFFICIAL_DOCS": _chunk_heading_aware,
    "GITHUB_PR_ISSUE": _chunk_paragraphs,
}


def chunk_document(document: SourceDocument, default_package: str | None = None) -> list[Chunk]:
    strategy = _STRATEGY_BY_SOURCE_TYPE.get(document.source_type, _chunk_paragraphs)
    return strategy(document, default_package)
