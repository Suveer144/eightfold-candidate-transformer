import pytest
from transformer.schema import FieldValue, RawRecord, Location, Experience, Education
from transformer.merger import group_records, merge_group


def _crm_record(email="alice@example.com", ye=5.0, name="Alice Johnson"):
    rec = RawRecord(source_name="crm", source_priority=3)
    rec.full_name = FieldValue(value=name, source="crm", priority=3, raw=name, method="stated")
    rec.emails = [FieldValue(value=email, source="crm", priority=3, raw=email, method="stated")]
    rec.years_experience = FieldValue(value=ye, source="crm", priority=3, raw=str(ye), method="stated")
    rec.location = FieldValue(
        value=Location(city="San Francisco", region="CA", country="US"),
        source="crm", priority=3, raw="SF", method="normalized",
    )
    rec.skills = [FieldValue(value="Python", source="crm", priority=3, raw="Python", method="stated")]
    rec.experience = [FieldValue(
        value=Experience(company="TechCorp", title="Data Scientist"),
        source="crm", priority=3, raw="Data Scientist@TechCorp", method="stated",
    )]
    return rec


def _notes_record(email="alice@example.com", extra_email="alice.work@gmail.com", ye=7.0, name="Alice Johnson"):
    rec = RawRecord(source_name="notes", source_priority=1)
    rec.full_name = FieldValue(value=name, source="notes", priority=1, raw=name, method="extracted")
    rec.emails = [
        FieldValue(value=email, source="notes", priority=1, raw=email, method="extracted"),
        FieldValue(value=extra_email, source="notes", priority=1, raw=extra_email, method="extracted"),
    ]
    rec.years_experience = FieldValue(value=ye, source="notes", priority=1, raw=f"{ye} years", method="extracted")
    rec.skills = [FieldValue(value="Spark", source="notes", priority=1, raw="Spark", method="extracted")]
    return rec


def _github_record(email="alice@example.com", name="Alice Johnson"):
    rec = RawRecord(source_name="github", source_priority=2)
    rec.full_name = FieldValue(value=name, source="github", priority=2, raw=name, method="stated")
    rec.emails = [FieldValue(value=email, source="github", priority=2, raw=email, method="supplied")]
    rec.experience = [FieldValue(
        value=Experience(company="TechCorp", title=None),
        source="github", priority=2, raw="TechCorp", method="stated",
    )]
    rec.skills = [FieldValue(value="Go", source="github", priority=2, raw="repo-lang", method="inferred")]
    return rec


# --- grouping tests -------------------------------------------------------

def test_same_email_groups_together():
    groups = group_records([_crm_record(), _notes_record()])
    assert len(groups) == 1


def test_different_emails_separate():
    groups = group_records([_crm_record(email="a@x.com"), _crm_record(email="b@x.com", name="Bob Jones")])
    assert len(groups) == 2


def test_name_fallback_grouping():
    r1 = RawRecord(source_name="crm", source_priority=3)
    r1.full_name = FieldValue(value="Alice Johnson", source="crm", priority=3, raw="Alice Johnson", method="stated")
    r2 = RawRecord(source_name="notes", source_priority=1)
    r2.full_name = FieldValue(value="Alice Johnson", source="notes", priority=1, raw="Alice Johnson", method="extracted")
    groups = group_records([r1, r2])
    assert len(groups) == 1


# --- merge tests ----------------------------------------------------------

def test_higher_priority_wins_scalar():
    profile = merge_group([_crm_record(ye=5.0), _notes_record(ye=7.0)])
    # CRM priority=3, notes priority=1 → CRM wins
    assert profile.years_experience == 5.0


def test_email_union():
    profile = merge_group([_crm_record(), _notes_record()])
    assert "alice@example.com" in profile.emails
    assert "alice.work@gmail.com" in profile.emails


def test_email_deduplication():
    profile = merge_group([_crm_record(), _notes_record()])
    assert profile.emails.count("alice@example.com") == 1


def test_skills_union():
    profile = merge_group([_crm_record(), _notes_record()])
    skill_names = {s.name for s in profile.skills}
    assert "Python" in skill_names
    assert "Spark" in skill_names


def test_skill_confidence_boosted_by_multiple_sources():
    crm = _crm_record()
    notes = _notes_record()
    notes.skills.append(FieldValue(value="Python", source="notes", priority=1, raw="Python", method="extracted"))
    profile = merge_group([crm, notes])
    python_skill = next(s for s in profile.skills if s.name == "Python")
    assert set(python_skill.sources) == {"crm", "notes"}
    assert python_skill.confidence > 0.9  # base 0.9 (stated) + source boost, capped at 1.0


def test_skill_confidence_single_inferred_source_lower():
    profile = merge_group([_github_record()])
    go_skill = next(s for s in profile.skills if s.name == "Go")
    assert go_skill.confidence == pytest.approx(0.5)  # inferred, single source


def test_conflict_logged():
    profile = merge_group([_crm_record(ye=5.0), _notes_record(ye=7.0)])
    conflict_fields = [c["field"] for c in profile.conflicts]
    assert "years_experience" in conflict_fields


def test_no_conflict_when_values_agree():
    profile = merge_group([_crm_record(ye=5.0), _notes_record(ye=5.0)])
    conflict_fields = [c["field"] for c in profile.conflicts]
    assert "years_experience" not in conflict_fields


def test_single_source_no_conflict():
    profile = merge_group([_crm_record()])
    assert profile.conflicts == []


def test_candidate_id_stable():
    p1 = merge_group([_crm_record()])
    p2 = merge_group([_crm_record()])
    assert p1.candidate_id == p2.candidate_id


def test_experience_dedup_by_company_title_conflict_logged():
    crm = _crm_record()  # TechCorp / Data Scientist, priority 3
    gh = _github_record()  # TechCorp / None, priority 2
    profile = merge_group([crm, gh])
    assert len(profile.experience) == 1  # same company -> merged, not duplicated
    assert profile.experience[0].company == "TechCorp"
    assert profile.experience[0].title == "Data Scientist"  # only crm stated a title


def test_three_way_priority_order():
    # crm(3) > github(2) > notes(1)
    profile = merge_group([_crm_record(), _github_record(), _notes_record()])
    assert profile.experience[0].title == "Data Scientist"  # from crm


def test_three_way_skills_union():
    profile = merge_group([_crm_record(), _github_record(), _notes_record()])
    skill_names = {s.name for s in profile.skills}
    assert "Python" in skill_names  # crm
    assert "Go" in skill_names      # github
    assert "Spark" in skill_names   # notes


def test_provenance_is_list_of_field_source_method():
    profile = merge_group([_crm_record(), _notes_record()])
    assert isinstance(profile.provenance, list)
    name_entries = [p for p in profile.provenance if p.field == "full_name"]
    assert len(name_entries) == 1
    assert name_entries[0].source == "crm"
    assert name_entries[0].method == "stated"


def test_education_fills_gaps_across_sources_not_first_wins():
    # Regression test: a lower-priority source (notes) stating the same
    # institution+degree with no end_year used to silently discard a
    # higher-priority source's (crm) stated end_year via naive dedup.
    crm = RawRecord(source_name="crm", source_priority=3)
    crm.full_name = FieldValue(value="Dana Lee", source="crm", priority=3, raw="Dana Lee", method="stated")
    crm.emails = [FieldValue(value="dana@example.com", source="crm", priority=3, raw="dana@example.com", method="stated")]
    crm.education = [FieldValue(
        value=Education(institution="MIT", degree="B.Tech", field="CS", end_year=2027),
        source="crm", priority=3, raw="2027", method="stated",
    )]

    notes = RawRecord(source_name="notes", source_priority=1)
    notes.full_name = FieldValue(value="Dana Lee", source="notes", priority=1, raw="Dana Lee", method="extracted")
    notes.emails = [FieldValue(value="dana@example.com", source="notes", priority=1, raw="dana@example.com", method="extracted")]
    notes.education = [FieldValue(
        value=Education(institution="MIT", degree="B.Tech", field=None, end_year=None),
        source="notes", priority=1, raw="MIT", method="extracted",
    )]

    profile = merge_group([crm, notes])
    assert len(profile.education) == 1
    assert profile.education[0].end_year == 2027  # filled from crm, not lost to notes' null
