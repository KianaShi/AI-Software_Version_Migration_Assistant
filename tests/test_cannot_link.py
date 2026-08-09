from src.aggregation import constraints
from src.entities.models import ChangeAttributes, Symbol

"""
Test the hard cannot-link constraints.

Each rule must be a deterministic structural comparison -- no similarity
scores involved. Verifies each of the four rules fires when it should,
stays silent when signals are simply unknown (None), and that priority
order picks the strongest signal when more than one rule could fire.
"""


def _attrs(
    symbol=None,
    version_from="2.0",
    version_to="3.0",
    change_type="REMOVED",
    summary="summary",
    external_refs=None,
):
    return ChangeAttributes(
        symbol=symbol or Symbol(name="requests.Session.verify", package="requests"),
        version_from=version_from,
        version_to=version_to,
        change_type=change_type,
        summary=summary,
        external_refs=external_refs if external_refs is not None else [],
    )


def test_explicit_different_references_triggers_cannot_link():
    a = _attrs(external_refs=["PR#100"])
    b = _attrs(external_refs=["PR#200"])

    result = constraints.check_explicit_different_references(a, b)

    assert result.allowed is False
    assert result.reason == "EXPLICIT_DIFFERENT_REFERENCE"


def test_explicit_different_references_allows_shared_ref():
    a = _attrs(external_refs=["PR#100"])
    b = _attrs(external_refs=["PR#100", "commit_abc"])

    assert constraints.check_explicit_different_references(a, b).allowed is True


def test_explicit_different_references_allows_when_one_side_unknown():
    a = _attrs(external_refs=[])
    b = _attrs(external_refs=["PR#100"])

    assert constraints.check_explicit_different_references(a, b).allowed is True


def test_incompatible_version_transition_triggers_cannot_link():
    a = _attrs(version_from="2.0", version_to="3.0")
    b = _attrs(version_from="4.0", version_to="5.0")

    result = constraints.check_incompatible_version_transition(a, b)

    assert result.allowed is False
    assert result.reason == "INCOMPATIBLE_VERSION_TRANSITION"


def test_incompatible_version_transition_allows_when_partially_unknown():
    a = _attrs(version_from="2.0", version_to="3.0")
    b = _attrs(version_from=None, version_to="3.0")

    assert constraints.check_incompatible_version_transition(a, b).allowed is True


def test_non_overlapping_change_semantics_triggers_cannot_link():
    a = _attrs(change_type="REMOVED")
    b = _attrs(change_type="RENAMED")

    result = constraints.check_non_overlapping_change_semantics(a, b)

    assert result.allowed is False
    assert result.reason == "NON_OVERLAPPING_SEMANTICS"


def test_non_overlapping_change_semantics_allows_same_type():
    a = _attrs(change_type="REMOVED")
    b = _attrs(change_type="REMOVED")

    assert constraints.check_non_overlapping_change_semantics(a, b).allowed is True


def test_behavior_changed_is_not_special_cased_and_cannot_links_by_default():
    # Stage 8A audit: BEHAVIOR_CHANGED must get the same conservative,
    # equality-based treatment as every other ChangeType -- no per-type
    # branch anywhere in constraints.py should exempt it.
    a = _attrs(change_type="BEHAVIOR_CHANGED")
    b = _attrs(change_type="SIGNATURE_CHANGED")

    result = constraints.check_non_overlapping_change_semantics(a, b)

    assert result.allowed is False
    assert result.reason == "NON_OVERLAPPING_SEMANTICS"


def test_behavior_changed_allows_same_type():
    a = _attrs(change_type="BEHAVIOR_CHANGED")
    b = _attrs(change_type="BEHAVIOR_CHANGED")

    assert constraints.check_non_overlapping_change_semantics(a, b).allowed is True


def test_separate_release_events_triggers_cannot_link():
    symbol = Symbol(name="timeout", package="requests")
    a = _attrs(symbol=symbol, version_to="3.0")
    b = _attrs(symbol=symbol, version_to="4.0")

    result = constraints.check_separate_release_events(a, b)

    assert result.allowed is False
    assert result.reason == "SEPARATE_RELEASE_EVENTS"


def test_separate_release_events_allows_different_symbol():
    a = _attrs(symbol=Symbol(name="timeout", package="requests"), version_to="3.0")
    b = _attrs(symbol=Symbol(name="verify", package="requests"), version_to="4.0")

    assert constraints.check_separate_release_events(a, b).allowed is True


def test_evaluate_cannot_link_returns_allowed_when_nothing_fires():
    a = _attrs()
    b = _attrs()

    result = constraints.evaluate_cannot_link(a, b)

    assert result.allowed is True


def test_evaluate_cannot_link_prioritizes_explicit_reference_over_version():
    # both an explicit-ref conflict and an incompatible version transition
    # are present; explicit reference must win since it's the strongest signal
    a = _attrs(version_from="2.0", version_to="3.0", external_refs=["PR#100"])
    b = _attrs(version_from="4.0", version_to="5.0", external_refs=["PR#200"])

    result = constraints.evaluate_cannot_link(a, b)

    assert result.reason == "EXPLICIT_DIFFERENT_REFERENCE"
