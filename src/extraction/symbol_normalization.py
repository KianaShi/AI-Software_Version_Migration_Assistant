import re
from dataclasses import dataclass

from src.entities.models import Symbol

"""
Deterministic symbol-mention finding and normalization.

Normalizes surface forms like `FooClient.create()`, `foo.FooClient.create`,
`FooClient#create`, and `FooClient::create` into a canonical dotted
Symbol(name, package, kind). This is intentionally conservative: backtick
code spans are the primary, most reliable signal; bare (non-backticked)
mentions are only recognized when they look unambiguously like a call
(`Class.method()`), to avoid false-positives on ordinary prose full of
dots and capitals.
"""


@dataclass
class SymbolMention:
    raw: str
    span: tuple[int, int]
    symbol: Symbol


_BACKTICK_RE = re.compile(r"`([^`]+)`")
_BARE_CALL_RE = re.compile(r"\b([A-Za-z_]\w*(?:[.:#]{1,2}[A-Za-z_]\w*)+\(\))")

# Deliberately excludes bare single words (e.g. `timeout`, a parameter name
# in backticks): a symbol needs either a dotted/scoped path (Foo.bar,
# Foo#bar, Foo::bar, with or without trailing parens) or a bare call
# (configure()). Without this, every backtick-quoted parameter name would
# be misread as its own symbol mention.
_LOOKS_LIKE_SYMBOL_RE = re.compile(
    r"^[A-Za-z_]\w*(?:[.:#]{1,2}[A-Za-z_]\w*)+\(?\)?$"
    r"|^[A-Za-z_]\w*\(\)$"
)


def normalize_symbol(raw: str, default_package: str | None = None) -> Symbol:
    text = raw.strip().strip("`")

    is_method = text.endswith("()") or "#" in text
    text = text[:-2] if text.endswith("()") else text
    text = text.replace("#", ".").replace("::", ".")

    package = default_package or ""
    if package and text.startswith(package + "."):
        name = text[len(package) + 1 :]
    else:
        name = text

    return Symbol(name=name, package=package, kind="method" if is_method else None)


def find_symbol_mentions(text: str, default_package: str | None = None) -> list[SymbolMention]:
    mentions: list[SymbolMention] = []
    claimed: list[tuple[int, int]] = []

    def _overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < end and start < span[1] for start, end in claimed)

    for match in _BACKTICK_RE.finditer(text):
        raw = match.group(1)
        if not _LOOKS_LIKE_SYMBOL_RE.match(raw):
            continue
        span = match.span()
        mentions.append(
            SymbolMention(raw=raw, span=span, symbol=normalize_symbol(raw, default_package))
        )
        claimed.append(span)

    for match in _BARE_CALL_RE.finditer(text):
        span = match.span()
        if _overlaps(span):
            continue
        raw = match.group(1)
        mentions.append(
            SymbolMention(raw=raw, span=span, symbol=normalize_symbol(raw, default_package))
        )
        claimed.append(span)

    mentions.sort(key=lambda m: m.span[0])
    return mentions
