"""
Calibratable constants for the Level 2 evidence-aggregation pipeline.

Everything in this file is a placeholder pending calibration against a gold
set. When tuning precision/recall, change these values -- not the logic in
constraints.py / pairwise.py.
"""

# --- pairwise scoring weights (combined via weighted sum, ideally sum to 1.0) ---
WEIGHT_SYMBOL_EXACT_MATCH = 0.35
WEIGHT_VERSION_COMPATIBILITY = 0.25
WEIGHT_CHANGE_TYPE_COMPATIBILITY = 0.15
WEIGHT_SUMMARY_SIMILARITY = 0.25

# --- decision thresholds on the weighted total score (0..1) ---
# total >= INFERRED_HIGH_CONFIDENCE_THRESHOLD           -> MATCH_INFERRED
# AMBIGUOUS_LOWER_BOUND <= total < ...THRESHOLD           -> AMBIGUOUS
# total < AMBIGUOUS_LOWER_BOUND                             -> NO_MATCH
INFERRED_HIGH_CONFIDENCE_THRESHOLD = 0.85
AMBIGUOUS_LOWER_BOUND = 0.55

# fixed confidence recorded for explicit-reference matches (never computed)
EXPLICIT_MATCH_CONFIDENCE = 1.0

# change_type pairs that may still describe the "same" underlying change
# despite not being identical (e.g. a lifecycle progression). Empty by
# default: precision-first means "different change_type" is treated as
# non-overlapping semantics unless a domain expert explicitly whitelists
# the pair here after reviewing real cases.
COMPATIBLE_CHANGE_TYPE_PAIRS: set[frozenset[str]] = set()
