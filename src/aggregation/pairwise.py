from dataclasses import dataclass, field

import numpy as np

from src.aggregation import config
from src.aggregation.constraints import ConstraintResult, evaluate_cannot_link
from src.embedding import generate_embeddings
from src.entities.models import ChangeAttributes, LinkMethod, PairwiseDecision

"""
Pairwise change resolution.

Symbol+package+version is only a blocking key (see blocking.py) -- deciding
whether two change candidates are actually the same change happens here,
and only two things can produce a MATCH: a shared explicit external
reference, or a scored comparison that clears a calibrated threshold.
Embedding similarity is one signal among several in that score, never the
sole basis for a merge.
"""


@dataclass
class PairwiseScore:
    total: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class PairwiseResult:
    decision: str  # PairwiseDecision value
    method: str    # LinkMethod value
    score: PairwiseScore
    rationale: str
    constraint: ConstraintResult


def _cosine_similarity(text_a: str, text_b: str) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0

    embeddings = generate_embeddings([text_a, text_b])
    vec_a, vec_b = embeddings[0], embeddings[1]

    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / denom)


def _score(unresolved: ChangeAttributes, candidate: ChangeAttributes) -> PairwiseScore:
    symbol_exact = (
        1.0
        if unresolved.symbol.name == candidate.symbol.name
        and unresolved.symbol.package == candidate.symbol.package
        else 0.0
    )
    version_compatible = (
        1.0
        if unresolved.version_to is None
        or candidate.version_to is None
        or unresolved.version_to == candidate.version_to
        else 0.0
    )
    change_type_match = 1.0 if unresolved.change_type == candidate.change_type else 0.0
    semantic_similarity = _cosine_similarity(unresolved.summary, candidate.summary)

    signals = {
        "symbol_exact": symbol_exact,
        "version_compatible": version_compatible,
        "change_type_match": change_type_match,
        "semantic_similarity": semantic_similarity,
    }

    total = (
        config.WEIGHT_SYMBOL_EXACT_MATCH * symbol_exact
        + config.WEIGHT_VERSION_COMPATIBILITY * version_compatible
        + config.WEIGHT_CHANGE_TYPE_COMPATIBILITY * change_type_match
        + config.WEIGHT_SUMMARY_SIMILARITY * semantic_similarity
    )

    return PairwiseScore(total=total, signals=signals)


def resolve(unresolved: ChangeAttributes, candidate: ChangeAttributes) -> PairwiseResult:
    """
    Resolve one (unresolved change, candidate change) pair.

    Order matters: cannot-link constraints are checked first and veto
    everything else regardless of score; an explicit shared reference is
    checked next and, if present, wins outright; only then does the
    weighted score decide MATCH_INFERRED / AMBIGUOUS / NO_MATCH.
    """
    constraint = evaluate_cannot_link(unresolved, candidate)

    if not constraint.allowed:
        return PairwiseResult(
            decision=PairwiseDecision.NO_MATCH.value,
            method=LinkMethod.PAIRWISE_RESOLUTION.value,
            score=PairwiseScore(total=0.0, signals={}),
            rationale=f"cannot-link ({constraint.reason}): {constraint.detail}",
            constraint=constraint,
        )

    shared_refs = set(unresolved.external_refs) & set(candidate.external_refs)
    if shared_refs:
        return PairwiseResult(
            decision=PairwiseDecision.MATCH_EXPLICIT.value,
            method=LinkMethod.EXPLICIT_REFERENCE.value,
            score=PairwiseScore(
                total=config.EXPLICIT_MATCH_CONFIDENCE,
                signals={"shared_external_refs": 1.0},
            ),
            rationale=f"shared external refs: {sorted(shared_refs)}",
            constraint=constraint,
        )

    score = _score(unresolved, candidate)

    if score.total >= config.INFERRED_HIGH_CONFIDENCE_THRESHOLD:
        decision = PairwiseDecision.MATCH_INFERRED.value
    elif score.total >= config.AMBIGUOUS_LOWER_BOUND:
        decision = PairwiseDecision.AMBIGUOUS.value
    else:
        decision = PairwiseDecision.NO_MATCH.value

    return PairwiseResult(
        decision=decision,
        method=LinkMethod.PAIRWISE_RESOLUTION.value,
        score=score,
        rationale=f"weighted score={score.total:.3f} signals={score.signals}",
        constraint=constraint,
    )
