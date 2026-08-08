from src.aggregation import pairwise
from src.entities.models import ChangeAttributes, LinkMethod, PairwiseDecision, Symbol

"""
Test pairwise change resolution.

Uses empty-string summaries to deterministically force semantic_similarity
to 0.0 (see pairwise._cosine_similarity), and identical non-empty summaries
to deterministically force it to ~1.0, so decision-band assertions don't
depend on the embedding model's exact output.
"""


def _attrs(
    name="requests.Session.verify",
    package="requests",
    version_from="2.0",
    version_to="3.0",
    change_type="REMOVED",
    summary="",
    external_refs=None,
):
    return ChangeAttributes(
        symbol=Symbol(name=name, package=package),
        version_from=version_from,
        version_to=version_to,
        change_type=change_type,
        summary=summary,
        external_refs=external_refs if external_refs is not None else [],
    )


def test_shared_explicit_reference_wins_outright():
    a = _attrs(external_refs=["PR#100"])
    b = _attrs(external_refs=["PR#100"])

    result = pairwise.resolve(a, b)

    assert result.decision == PairwiseDecision.MATCH_EXPLICIT.value
    assert result.method == LinkMethod.EXPLICIT_REFERENCE.value


def test_cannot_link_short_circuits_even_with_identical_summaries():
    # summaries are identical (would otherwise score ~1.0), but refs conflict
    a = _attrs(summary="verify parameter removed", external_refs=["PR#100"])
    b = _attrs(summary="verify parameter removed", external_refs=["PR#200"])

    result = pairwise.resolve(a, b)

    assert result.decision == PairwiseDecision.NO_MATCH.value
    assert result.constraint.allowed is False
    assert "cannot-link" in result.rationale


def test_high_score_yields_match_inferred():
    a = _attrs(summary="verify parameter removed")
    b = _attrs(summary="verify parameter removed")

    result = pairwise.resolve(a, b)

    assert result.decision == PairwiseDecision.MATCH_INFERRED.value
    assert result.method == LinkMethod.PAIRWISE_RESOLUTION.value
    assert result.score.signals["semantic_similarity"] > 0.99


def test_mid_score_yields_ambiguous():
    # same symbol/version/change_type but zero semantic similarity (empty
    # summary on one side): total = 0.35 + 0.25 + 0.15 + 0 = 0.75
    a = _attrs(summary="verify parameter removed")
    b = _attrs(summary="")

    result = pairwise.resolve(a, b)

    assert result.decision == PairwiseDecision.AMBIGUOUS.value
    assert 0.55 <= result.score.total < 0.85


def test_low_score_yields_no_match():
    # different symbol, zero semantic similarity: total = 0 + 0.25 + 0.15 + 0 = 0.40
    a = _attrs(name="requests.Session.verify", version_to=None)
    b = _attrs(name="requests.Session.timeout", version_to=None)

    result = pairwise.resolve(a, b)

    assert result.decision == PairwiseDecision.NO_MATCH.value
    assert result.score.total < 0.55
