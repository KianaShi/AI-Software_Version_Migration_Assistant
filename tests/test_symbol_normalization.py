from src.entities.models import Symbol
from src.extraction.symbol_normalization import find_symbol_mentions, normalize_symbol

"""
Test symbol normalization: FooClient.create(), foo.FooClient.create,
FooClient#create, FooClient::create should all normalize to the same
canonical Symbol, and backtick-quoted plain words (parameter names) must
not be misread as symbols.
"""


def test_dotted_call_normalizes():
    symbol = normalize_symbol("FooClient.create()", default_package="foo")

    assert symbol == Symbol(name="FooClient.create", package="foo", kind="method")


def test_package_prefixed_dotted_path_normalizes():
    symbol = normalize_symbol("foo.FooClient.create", default_package="foo")

    assert symbol == Symbol(name="FooClient.create", package="foo", kind=None)


def test_hash_style_normalizes():
    symbol = normalize_symbol("FooClient#create", default_package="foo")

    assert symbol == Symbol(name="FooClient.create", package="foo", kind="method")


def test_double_colon_style_normalizes():
    symbol = normalize_symbol("FooClient::create", default_package="foo")

    assert symbol == Symbol(name="FooClient.create", package="foo", kind=None)


def test_all_forms_agree_on_canonical_name():
    forms = ["FooClient.create()", "foo.FooClient.create", "FooClient#create", "FooClient::create"]
    names = {normalize_symbol(f, default_package="foo").name for f in forms}

    assert names == {"FooClient.create"}


def test_unknown_package_defaults_to_empty_string():
    symbol = normalize_symbol("FooClient.create()")

    assert symbol.package == ""


def test_find_symbol_mentions_prefers_backtick_spans():
    mentions = find_symbol_mentions("The `FooClient.create()` method changed.")

    assert len(mentions) == 1
    assert mentions[0].symbol.name == "FooClient.create"


def test_find_symbol_mentions_accepts_bare_call_without_backticks():
    mentions = find_symbol_mentions("FooClient.create() was removed.")

    assert len(mentions) == 1
    assert mentions[0].symbol.name == "FooClient.create"


def test_find_symbol_mentions_ignores_bare_word_in_backticks():
    mentions = find_symbol_mentions("The `timeout` value changed.")

    assert mentions == []


def test_find_symbol_mentions_ignores_ordinary_prose():
    mentions = find_symbol_mentions("This library is great, e.g. see our docs.")

    assert mentions == []


def test_find_symbol_mentions_finds_multiple_distinct_symbols():
    mentions = find_symbol_mentions("`FooClient.create()` and `BarClient.build()` both changed.")

    names = {m.symbol.name for m in mentions}
    assert names == {"FooClient.create", "BarClient.build"}
