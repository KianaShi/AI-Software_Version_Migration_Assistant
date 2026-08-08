from dataclasses import dataclass

from src.aggregation import config
from src.entities.models import CannotLinkReason, ChangeAttributes

"""
Hard cannot-link constraints.

Every check here is a deterministic comparison over structured fields
(change_type, version_from/to, external_refs, symbol identity) -- never a
similarity score or embedding distance. Similarity-based signals belong in
pairwise.py's scoring, not here: a cannot-link veto has to be explainable
without reference to a threshold that might shift under calibration.
"""


@dataclass
class ConstraintResult:
    allowed: bool
    reason: str | None = None   # CannotLinkReason value, set when allowed=False
    detail: str | None = None   # human-readable specifics, for provenance/debugging


def check_explicit_different_references(
    a: ChangeAttributes, b: ChangeAttributes
) -> ConstraintResult:
    """Strongest signal: both sides name explicit refs, and they disagree."""
    refs_a, refs_b = set(a.external_refs), set(b.external_refs)

    if refs_a and refs_b and refs_a.isdisjoint(refs_b):
        return ConstraintResult(
            allowed=False,
            reason=CannotLinkReason.EXPLICIT_DIFFERENT_REFERENCE.value,
            detail=f"disjoint external refs: {sorted(refs_a)} vs {sorted(refs_b)}",
        )

    return ConstraintResult(allowed=True)


def check_incompatible_version_transition(
    a: ChangeAttributes, b: ChangeAttributes
) -> ConstraintResult:
    """Both sides name a full version_from->version_to transition, and they differ."""
    if (
        a.version_from
        and b.version_from
        and a.version_from != b.version_from
        and a.version_to
        and b.version_to
        and a.version_to != b.version_to
    ):
        return ConstraintResult(
            allowed=False,
            reason=CannotLinkReason.INCOMPATIBLE_VERSION_TRANSITION.value,
            detail=(
                f"{a.version_from}->{a.version_to} vs {b.version_from}->{b.version_to}"
            ),
        )

    return ConstraintResult(allowed=True)


def check_non_overlapping_change_semantics(
    a: ChangeAttributes, b: ChangeAttributes
) -> ConstraintResult:
    """Same symbol can still describe two unrelated kinds of change."""
    if (
        a.change_type != b.change_type
        and frozenset({a.change_type, b.change_type})
        not in config.COMPATIBLE_CHANGE_TYPE_PAIRS
    ):
        return ConstraintResult(
            allowed=False,
            reason=CannotLinkReason.NON_OVERLAPPING_SEMANTICS.value,
            detail=(
                f"change_type {a.change_type!r} vs {b.change_type!r} not in "
                "compatible-pair allowlist"
            ),
        )

    return ConstraintResult(allowed=True)


def check_separate_release_events(
    a: ChangeAttributes, b: ChangeAttributes
) -> ConstraintResult:
    """
    Guards against merging on symbol/parameter name alone: the same symbol
    showing up with two different version_to values is two release events,
    not one, even though blocking put them in the same candidate set.
    """
    same_symbol = a.symbol.name == b.symbol.name and a.symbol.package == b.symbol.package

    if same_symbol and a.version_to and b.version_to and a.version_to != b.version_to:
        return ConstraintResult(
            allowed=False,
            reason=CannotLinkReason.SEPARATE_RELEASE_EVENTS.value,
            detail=(
                f"same symbol {a.symbol.name!r}, different version_to: "
                f"{a.version_to} vs {b.version_to}"
            ),
        )

    return ConstraintResult(allowed=True)


# Priority order matters: the strongest, most explicit signal is checked
# first so its `reason`/`detail` wins when multiple constraints would fire.
_CHECKS_IN_PRIORITY_ORDER = [
    check_explicit_different_references,
    check_incompatible_version_transition,
    check_non_overlapping_change_semantics,
    check_separate_release_events,
]


def evaluate_cannot_link(a: ChangeAttributes, b: ChangeAttributes) -> ConstraintResult:
    """Run all hard constraints; return the first one that vetoes a link."""
    for check in _CHECKS_IN_PRIORITY_ORDER:
        result = check(a, b)
        if not result.allowed:
            return result

    return ConstraintResult(allowed=True)
