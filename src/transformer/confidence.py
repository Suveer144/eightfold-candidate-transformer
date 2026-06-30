from __future__ import annotations
from .schema import CanonicalProfile

# Weights must sum to 1.0
_WEIGHTS: dict[str, float] = {
    "full_name":        0.25,
    "emails":           0.20,
    "skills":           0.15,
    "phones":           0.10,
    "location":         0.10,
    "years_experience": 0.10,
    "experience":       0.10,
}

_NORM_FAILURE_PENALTY = 0.05   # per failed normalization (phone/date that couldn't parse)
_CONFLICT_PENALTY     = 0.05   # per inter-source conflict detected

DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.4


def compute_confidence(profile: CanonicalProfile) -> float:
    """
    Weighted completeness score over required fields.
    Penalties applied for normalization failures and source conflicts.
    Result is clamped to [0.0, 1.0].

    Formula:
      base   = sum(weight for each required field that is non-null/non-empty)
      penalty = norm_failures * 0.05 + conflicts * 0.05
      score  = clamp(base - penalty, 0, 1)
    """
    base = 0.0
    for field_name, weight in _WEIGHTS.items():
        val = getattr(profile, field_name)
        if val is not None and val != [] and val != "":
            base += weight

    norm_failures = sum(
        1 for w in profile.warnings
        if "Could not" in w or "Invalid phone" in w or "Empty phone" in w
    )
    conflict_count = len(profile.conflicts)
    penalty = norm_failures * _NORM_FAILURE_PENALTY + conflict_count * _CONFLICT_PENALTY

    return round(max(0.0, min(1.0, base - penalty)), 4)


def is_low_confidence(score: float, threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD) -> bool:
    return score < threshold
