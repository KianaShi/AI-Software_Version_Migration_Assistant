from src.entities.models import ChangeType
from src.extraction.change_extraction import extract_changes
from src.extraction.models import ExtractionConfidence
from src.extraction.sources import parse_release_note

"""
Test the deterministic Level 1 change-extraction pipeline.

The positive cases confirm well-formed statements produce a correct
UnresolvedChange. The negative/adversarial cases are the point of this
module: a careless extractor would over-extract on a mere mention, merge
two independent changes into one garbled record, or misread a
co-mentioned old/new API pair. None of that should happen here -- when
extraction can't cleanly attribute a claim, it must emit nothing rather
than guess (Level 1 is precision-first too, same as Level 2).
"""


def _doc(text, version=None, default_package="foo"):
    return parse_release_note(text, version=version), default_package


def test_replacement_statement_yields_one_change_with_replacement_symbol():
    doc, pkg = _doc("In v5, `FooClient.create()` was replaced by `FooClient.build()`.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    change = changes[0]
    assert change.symbol.name == "FooClient.create"
    assert change.change_type == ChangeType.REPLACEMENT.value
    assert change.replacement_symbol == "FooClient.build"
    assert change.version_to == "5"
    assert change.extraction_confidence == ExtractionConfidence.EXPLICIT.value


def test_moved_to_statement_yields_one_change_with_replacement_symbol():
    doc, pkg = _doc("`foo.OldThing` was moved to `foo_extra.OldThing` in v5.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    change = changes[0]
    assert change.symbol.name == "OldThing"
    assert change.change_type == ChangeType.MOVED.value
    assert change.replacement_symbol == "foo_extra.OldThing"


def test_deprecated_in_favor_of_captures_replacement_without_merging():
    doc, pkg = _doc("`FooClient.create()` is deprecated in favor of `FooClient.build()`.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.DEPRECATED.value
    assert changes[0].replacement_symbol == "FooClient.build"


def test_two_independent_changes_in_one_statement_are_split_not_merged():
    doc, pkg = _doc("`FooClient.create()` was removed and `BarClient.build()` was renamed.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 2
    by_symbol = {c.symbol.name: c for c in changes}
    assert by_symbol["FooClient.create"].change_type == ChangeType.REMOVED.value
    assert by_symbol["BarClient.build"].change_type == ChangeType.RENAMED.value
    # each change's summary must not have absorbed the other symbol's clause
    assert "BarClient" not in by_symbol["FooClient.create"].summary
    assert "FooClient" not in by_symbol["BarClient.build"].summary


def test_mere_mention_of_a_symbol_extracts_nothing():
    doc, pkg = _doc("`FooClient.create()` is used to instantiate a new client.")

    assert extract_changes(doc, default_package=pkg) == []


def test_old_and_new_api_merely_co_mentioned_extracts_nothing():
    doc, pkg = _doc(
        "Both `FooClient.create()` and `FooClient.build()` are available for creating clients."
    )

    assert extract_changes(doc, default_package=pkg) == []


def test_change_keyword_without_any_symbol_extracts_nothing():
    doc, pkg = _doc("This release removed a lot of technical debt.")

    assert extract_changes(doc, default_package=pkg) == []


def test_version_only_in_parent_heading_is_used_but_marked_inferred():
    text = "## v5.0.0\n- `FooClient.create()` was removed.\n"
    doc, pkg = _doc(text)

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    change = changes[0]
    assert change.version_to == "5.0.0"
    assert change.extraction_confidence == ExtractionConfidence.INFERRED.value
    assert "ambient_version" in change.extraction_method


def test_inline_version_is_explicit_confidence():
    doc, pkg = _doc("`FooClient.create()` was removed in v5.0.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    assert changes[0].extraction_confidence == ExtractionConfidence.EXPLICIT.value
    assert "inline_version" in changes[0].extraction_method


def test_no_version_anywhere_still_extracts_with_inferred_confidence():
    doc, pkg = _doc("`FooClient.create()` was removed.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    assert changes[0].version_to is None
    assert changes[0].extraction_confidence == ExtractionConfidence.INFERRED.value


def test_signature_changed_captures_named_parameter():
    doc, pkg = _doc("`FooClient.create()` no longer accepts the `timeout` parameter.")

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    change = changes[0]
    assert change.change_type == ChangeType.SIGNATURE_CHANGED.value
    assert change.parameters == ["timeout"]


def test_action_clause_captured_when_no_clean_replacement_symbol():
    # Stage 8A.1: not every migration is a symbol->symbol rename; a
    # trailing "; ... instead" clause should still surface as a
    # free-text recommended action even when replacement_symbol is None.
    doc, pkg = _doc(
        "`pydantic.dataclasses` validation behavior changed in v2.0.0: "
        "tuples are no longer accepted as input for nested fields; use dicts instead."
    )

    changes = extract_changes(doc, default_package=pkg)

    assert len(changes) == 1
    assert changes[0].replacement_symbol is None
    assert changes[0].migration_action_text == "use dicts instead"


def test_action_clause_none_when_statement_has_no_instead_clause():
    doc, pkg = _doc("`FooClient.create()` was removed.")

    changes = extract_changes(doc, default_package=pkg)

    assert changes[0].migration_action_text is None


def test_external_ref_in_text_is_captured():
    doc, pkg = _doc("`FooClient.create()` was removed (#4213).")

    changes = extract_changes(doc, default_package=pkg)

    assert changes[0].external_refs == ["#4213"]


def test_document_level_ref_propagates_to_extracted_change():
    from src.extraction.sources import parse_github_pr_issue

    doc = parse_github_pr_issue(
        "`FooClient.create()` was removed.", reference="PR#100"
    )

    changes = extract_changes(doc, default_package="foo")

    assert changes[0].external_refs == ["PR#100"]


def test_never_generates_a_change_id():
    doc, pkg = _doc("`FooClient.create()` was removed.")

    changes = extract_changes(doc, default_package=pkg)

    assert not hasattr(changes[0], "change_id")


def test_llm_fallback_is_not_invoked_without_a_configured_extractor():
    doc, pkg = _doc("Note: `FooClient.create()` behavior may be affected by recent changes.")

    # no llm_extractor passed -> default None -> must not raise, must not guess
    assert extract_changes(doc, default_package=pkg) == []


def test_llm_fallback_is_invoked_only_for_ambiguous_signal_statements():
    class RecordingExtractor:
        def __init__(self):
            self.calls = []

        def extract(self, statement, document):
            self.calls.append(statement)
            return []

    extractor = RecordingExtractor()
    doc, pkg = _doc("Note: `FooClient.create()` behavior may be affected by recent changes.")

    extract_changes(doc, default_package=pkg, llm_extractor=extractor)

    assert len(extractor.calls) == 1

    extractor.calls.clear()
    plain_doc, _ = _doc("`FooClient.create()` is used to instantiate a new client.")
    extract_changes(plain_doc, default_package=pkg, llm_extractor=extractor)

    assert extractor.calls == []
