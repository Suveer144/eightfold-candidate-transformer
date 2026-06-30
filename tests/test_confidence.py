import pytest
from transformer.schema import CanonicalProfile, Location, Skill, Experience
from transformer.confidence import compute_confidence, is_low_confidence, DEFAULT_LOW_CONFIDENCE_THRESHOLD


def _full_profile(**overrides) -> CanonicalProfile:
    p = CanonicalProfile(
        candidate_id="CTEST",
        full_name="Alice Johnson",
        emails=["alice@example.com"],
        phones=["+14155550101"],
        location=Location(city="San Francisco", region="CA", country="US"),
        skills=[Skill(name="Python", confidence=0.9, sources=["crm"])],
        years_experience=5.0,
        experience=[Experience(company="TechCorp", title="Data Scientist")],
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def test_full_profile_near_perfect():
    score = compute_confidence(_full_profile())
    assert score >= 0.95


def test_missing_name_lowers_score():
    score = compute_confidence(_full_profile(full_name=None))
    full = compute_confidence(_full_profile())
    assert score < full
    assert score == pytest.approx(full - 0.25, abs=0.01)


def test_missing_email_lowers_score():
    score = compute_confidence(_full_profile(emails=[]))
    full = compute_confidence(_full_profile())
    assert score < full


def test_missing_experience_lowers_score():
    score = compute_confidence(_full_profile(experience=[]))
    full = compute_confidence(_full_profile())
    assert score < full
    assert score == pytest.approx(full - 0.10, abs=0.01)


def test_normalization_failure_penalises():
    profile = _full_profile()
    profile.warnings = ["Could not parse phone '(bad)'"]
    score = compute_confidence(profile)
    clean = compute_confidence(_full_profile())
    assert score < clean


def test_conflict_penalises():
    profile = _full_profile()
    profile.conflicts = [{"field": "years_experience"}]
    score = compute_confidence(profile)
    clean = compute_confidence(_full_profile())
    assert score < clean


def test_score_bounded():
    profile = _full_profile()
    profile.warnings = ["Could not parse phone"] * 50
    profile.conflicts = [{"field": "x"}] * 50
    score = compute_confidence(profile)
    assert 0.0 <= score <= 1.0


def test_empty_profile_zero():
    profile = CanonicalProfile(candidate_id="X")
    score = compute_confidence(profile)
    assert score == 0.0


def test_low_confidence_flag():
    assert is_low_confidence(0.2)
    assert not is_low_confidence(0.9)
    assert is_low_confidence(DEFAULT_LOW_CONFIDENCE_THRESHOLD - 0.01)
    assert not is_low_confidence(DEFAULT_LOW_CONFIDENCE_THRESHOLD)
