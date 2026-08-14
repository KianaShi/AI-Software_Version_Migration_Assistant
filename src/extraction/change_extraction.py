import re

from src.entities.models import ChangeType, UnresolvedChange
from src.extraction.llm_fallback import LLMExtractor
from src.extraction.models import ExtractionConfidence, SourceDocument
from src.extraction.symbol_normalization import find_symbol_mentions, normalize_symbol
from src.extraction.version_normalization import (
    VersionMention,
    VersionQualifier,
    find_version_mentions,
)

"""
Deterministic-first Level 1 change extraction.

extract_changes() answers only "what does this piece of evidence claim?"
-- symbol, change_type, version, parameters, replacement -- and always
emits UnresolvedChange, never a change_id. Which existing ChangeRecord (if
any) this claim belongs to is decided later by aggregation/linker.py, not
here.

Rules, in order of priority:
1. A statement with no recognized change-verb is not a change (a symbol
   being merely mentioned is not evidence of a change).
2. A statement with a change-verb but no attributable symbol is dropped
   rather than guessed.
3. A statement naming exactly one symbol is a single claim.
4. A statement naming more than one symbol is first checked against the
   replacement-style patterns (old X replaced by / deprecated in favor of
   new Y) which are legitimately one claim about two symbols; failing
   that, it is split once on conjunctions and each half is re-evaluated
   independently, so two independent changes in one paragraph produce two
   UnresolvedChange records instead of one merged/garbled one.
5. Anything a change-verb-bearing statement can't cleanly resolve is
   dropped, unless an LLMExtractor is supplied and the statement contains
   an ambiguous-but-plausible signal word -- deterministic rules never
   silently guess.
"""

_SYMBOL_TOKEN = r"`[^`]+`|[A-Za-z_]\w*(?:[.:#]{1,2}[A-Za-z_]\w*)+\(\)"

_REPLACEMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            rf"(?P<old>{_SYMBOL_TOKEN})\s+(?:was|is|has been)\s+replaced\s+(?:by|with)\s+(?P<new>{_SYMBOL_TOKEN})",
            re.IGNORECASE,
        ),
        ChangeType.REPLACEMENT.value,
    ),
    (
        re.compile(
            rf"(?P<old>{_SYMBOL_TOKEN})\s+(?:is|was)\s+deprecated\s+in favor of\s+(?P<new>{_SYMBOL_TOKEN})",
            re.IGNORECASE,
        ),
        ChangeType.DEPRECATED.value,
    ),
    (
        re.compile(
            rf"use\s+(?P<new>{_SYMBOL_TOKEN})\s+instead of\s+(?P<old>{_SYMBOL_TOKEN})",
            re.IGNORECASE,
        ),
        ChangeType.DEPRECATED.value,
    ),
    (
        re.compile(
            rf"(?P<old>{_SYMBOL_TOKEN})\s+was\s+moved\s+to\s+(?P<new>{_SYMBOL_TOKEN})",
            re.IGNORECASE,
        ),
        ChangeType.MOVED.value,
    ),
]

# Most-specific phrase first: "no longer accepts" must win over the
# generic "no longer" fallback, etc.
_CHANGE_TYPE_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bno longer accepts?\b", re.IGNORECASE), ChangeType.SIGNATURE_CHANGED.value),
    (re.compile(r"\bnow requires\b", re.IGNORECASE), ChangeType.SIGNATURE_CHANGED.value),
    (re.compile(r"\bnew (?:required )?parameter\b", re.IGNORECASE), ChangeType.SIGNATURE_CHANGED.value),
    (re.compile(r"\bchanged signature\b", re.IGNORECASE), ChangeType.SIGNATURE_CHANGED.value),
    (re.compile(r"\bnow returns\b", re.IGNORECASE), ChangeType.BEHAVIOR_CHANGED.value),
    (re.compile(r"\bnow throws\b", re.IGNORECASE), ChangeType.BEHAVIOR_CHANGED.value),
    (re.compile(r"\bbehavior (?:has )?changed\b", re.IGNORECASE), ChangeType.BEHAVIOR_CHANGED.value),
    (re.compile(r"\bmoved to\b", re.IGNORECASE), ChangeType.MOVED.value),
    (re.compile(r"\brelocated\b", re.IGNORECASE), ChangeType.MOVED.value),
    (re.compile(r"\bdeprecated\b", re.IGNORECASE), ChangeType.DEPRECATED.value),
    (re.compile(r"\brenamed\b", re.IGNORECASE), ChangeType.RENAMED.value),
    (re.compile(r"\bnow (?:called|named)\b", re.IGNORECASE), ChangeType.RENAMED.value),
    (re.compile(r"\bremoved\b", re.IGNORECASE), ChangeType.REMOVED.value),
    (re.compile(r"\bno longer\b", re.IGNORECASE), ChangeType.BEHAVIOR_CHANGED.value),
]

_PARAMETER_RE = re.compile(r"`([^`]+)`\s+parameter|parameter\s+`([^`]+)`", re.IGNORECASE)
# Trailing "; ... instead[.]" clause: catches recommended actions that
# aren't a clean symbol->symbol rename (e.g. "use dicts instead",
# "subclass BaseModel and Generic directly instead") and so never
# populate replacement_symbol. Applied universally in _build_change,
# regardless of which extraction path produced the statement.
_ACTION_CLAUSE_RE = re.compile(r";\s*([^;]*?\binstead\b[^;]*?)\.?\s*$", re.IGNORECASE)
_EXTERNAL_REF_RE = re.compile(
    r"\bPR\s*#?(\d+)\b|\bGH-(\d+)\b|\bissue\s*#?(\d+)\b|\(#(\d+)\)", re.IGNORECASE
)
_HEADING_RE = re.compile(r"^#{1,6}\s*(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
_CONJUNCTION_SPLIT_RE = re.compile(r"\s*(?:;|\band\b)\s*", re.IGNORECASE)
_AMBIGUOUS_SIGNAL_WORDS = re.compile(
    r"\b(?:breaking|note|warning|updated|modified|change[ds]?)\b", re.IGNORECASE
)


def _match_change_type(statement: str) -> str | None:
    for pattern, change_type in _CHANGE_TYPE_KEYWORDS:
        if pattern.search(statement):
            return change_type
    return None


def _find_parameters(statement: str) -> list[str]:
    params = []
    for match in _PARAMETER_RE.finditer(statement):
        name = match.group(1) or match.group(2)
        if name:
            params.append(name)
    return params


def _find_action_clause(statement: str) -> str | None:
    match = _ACTION_CLAUSE_RE.search(statement)
    if match:
        return match.group(1).strip()
    return None


def _find_external_refs(text: str) -> list[str]:
    refs = []
    for match in _EXTERNAL_REF_RE.finditer(text):
        # _EXTERNAL_REF_RE is a top-level alternation with exactly one
        # capturing group per branch, each requiring \d+ (no empty
        # captures) -- a successful match structurally guarantees
        # exactly one group is non-None. Not provable by static
        # analysis, so make the invariant explicit rather than relying
        # on next()'s bare StopIteration to fail loudly enough.
        number = next((g for g in match.groups() if g is not None), None)
        if number is None:
            raise ValueError(
                "External reference regex matched without a captured reference number"
            )
        refs.append(f"#{number}")
    return refs


def _version_mention_to_from_to(mention: VersionMention) -> tuple[str | None, str | None]:
    if mention.qualifier == VersionQualifier.RANGE.value:
        return mention.normalized, mention.normalized_end
    if mention.qualifier == VersionQualifier.SINCE.value:
        return mention.normalized, None
    return None, mention.normalized  # EXACT: the change takes effect at this version


def _resolve_version(
    statement: str, ambient_version: str | None
) -> tuple[str | None, str | None, bool]:
    """Returns (version_from, version_to, came_from_inline_mention)."""
    mentions = find_version_mentions(statement)
    if mentions:
        version_from, version_to = _version_mention_to_from_to(mentions[0])
        return version_from, version_to, True
    if ambient_version is not None:
        return None, ambient_version, False
    return None, None, False


def _split_into_sections(text: str) -> list[tuple[str | None, str]]:
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


def _split_into_statements(body: str) -> list[str]:
    bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
    if bullets:
        return [b for b in bullets if b]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]


def _build_change(
    statement: str,
    symbol,
    change_type: str,
    replacement_symbol: str | None,
    parameters: list[str],
    ambient_version: str | None,
    document: SourceDocument,
    method_prefix: str,
) -> UnresolvedChange:
    version_from, version_to, is_inline = _resolve_version(statement, ambient_version)
    external_refs = list(
        dict.fromkeys(_find_external_refs(statement) + document.document_refs)
    )

    if is_inline:
        confidence = ExtractionConfidence.EXPLICIT.value
        method = f"{method_prefix}+inline_version"
    elif version_to or version_from:
        confidence = ExtractionConfidence.INFERRED.value
        method = f"{method_prefix}+ambient_version"
    else:
        confidence = ExtractionConfidence.INFERRED.value
        method = f"{method_prefix}+no_version"

    return UnresolvedChange(
        symbol=symbol,
        version_from=version_from,
        version_to=version_to,
        change_type=change_type,
        summary=statement,
        external_refs=external_refs,
        replacement_symbol=replacement_symbol,
        parameters=parameters,
        migration_action_text=_find_action_clause(statement),
        source_type=document.source_type,
        source_document_id=document.document_id,
        raw_text=statement,
        extraction_confidence=confidence,
        extraction_method=method,
    )


def _extract_replacement(
    statement: str, ambient_version: str | None, document: SourceDocument, default_package: str | None
) -> UnresolvedChange | None:
    for pattern, change_type in _REPLACEMENT_PATTERNS:
        match = pattern.search(statement)
        if not match:
            continue
        symbol = normalize_symbol(match.group("old"), default_package)
        replacement_symbol = normalize_symbol(match.group("new"), default_package).name
        return _build_change(
            statement, symbol, change_type, replacement_symbol, [], ambient_version, document,
            "regex:replacement_pattern",
        )
    return None


def _extract_single_symbol(
    statement: str, ambient_version: str | None, document: SourceDocument, default_package: str | None
) -> UnresolvedChange | None:
    change_type = _match_change_type(statement)
    if change_type is None:
        return None

    symbol_mentions = find_symbol_mentions(statement, default_package)
    if len(symbol_mentions) != 1:
        return None

    parameters = (
        _find_parameters(statement) if change_type == ChangeType.SIGNATURE_CHANGED.value else []
    )
    return _build_change(
        statement, symbol_mentions[0].symbol, change_type, None, parameters,
        ambient_version, document, "regex:change_keyword",
    )


def _extract_from_statement(
    statement: str,
    ambient_version: str | None,
    document: SourceDocument,
    default_package: str | None,
    llm_extractor: LLMExtractor | None,
    allow_split: bool = True,
) -> list[UnresolvedChange]:
    replacement = _extract_replacement(statement, ambient_version, document, default_package)
    if replacement is not None:
        return [replacement]

    single = _extract_single_symbol(statement, ambient_version, document, default_package)
    if single is not None:
        return [single]

    change_type = _match_change_type(statement)
    symbol_mentions = find_symbol_mentions(statement, default_package)

    if change_type is not None and len(symbol_mentions) > 1 and allow_split:
        parts = [p for p in _CONJUNCTION_SPLIT_RE.split(statement) if p.strip()]
        if len(parts) > 1:
            results: list[UnresolvedChange] = []
            for part in parts:
                results.extend(
                    _extract_from_statement(
                        part, ambient_version, document, default_package, llm_extractor,
                        allow_split=False,
                    )
                )
            if results:
                return results

    if change_type is None and symbol_mentions and llm_extractor is not None:
        if _AMBIGUOUS_SIGNAL_WORDS.search(statement):
            return llm_extractor.extract(statement, document)

    return []


def extract_changes(
    document: SourceDocument,
    default_package: str | None = None,
    llm_extractor: LLMExtractor | None = None,
) -> list[UnresolvedChange]:
    changes: list[UnresolvedChange] = []

    for section_version, body in _split_into_sections(document.raw_text):
        ambient_version = section_version or document.version
        for statement in _split_into_statements(body):
            changes.extend(
                _extract_from_statement(
                    statement, ambient_version, document, default_package, llm_extractor
                )
            )

    return changes
