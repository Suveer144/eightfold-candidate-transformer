import pytest
from transformer.sources.notes import NotesSource

_SINGLE = """\
Spoke with Alice Johnson today. She's currently working as a Senior Data Scientist at TechCorp.
Based in San Francisco, CA. Claims about 7 years of total experience.
Skills include Python, machine learning, and SQL.
Her email is alice@example.com and cell is (415) 555-0101.
"""

_MULTI = """\
Spoke with Alice Johnson. Email: alice@example.com. Currently a Data Scientist. Based in SF, CA.
Skills: Python, SQL. 5 years of experience.

---

Candidate Bob Smith. Email: bob@example.com. Currently: Backend Engineer at StartupXYZ, New York, NY.
Skills: Go, Rust. 4+ years exp.
"""

_NO_NAME = "No name here. Skills: Python. email: nobody@example.com. Phone: (415) 555-1234."

_RANGE_YE = "Spoke with Jane Doe. She has 3-5 years of experience. Email: jane@example.com."

_NOTES_BLOCK = """\
Notes for David Lee. Phone: 408-555-0201. Lives in San Jose, CA.
Experience with Python, Django, REST APIs. About 2 years of experience.
Currently a Junior Developer.
"""


def test_single_block_parsed(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    records = NotesSource().parse(str(f))
    assert len(records) == 1


def test_name_extracted(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert r.full_name.value == "Alice Johnson"


def test_email_extracted(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert any(fv.value == "alice@example.com" for fv in r.emails)


def test_current_role_becomes_experience(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert len(r.experience) == 1
    exp = r.experience[0].value
    assert exp.title == "Senior Data Scientist"
    assert exp.company == "TechCorp"


def test_years_experience(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert r.years_experience.value == 7.0


def test_location(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert r.location.value.city == "San Francisco"
    assert r.location.value.region == "CA"


def test_skills(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    skill_values = [fv.value.lower() for fv in r.skills]
    assert "python" in skill_values


def test_multi_block(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_MULTI, encoding="utf-8")
    records = NotesSource().parse(str(f))
    assert len(records) == 2
    names = {r.full_name.value for r in records}
    assert "Alice Johnson" in names
    assert "Bob Smith" in names


def test_multi_block_role_and_company(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_MULTI, encoding="utf-8")
    records = NotesSource().parse(str(f))
    bob = next(r for r in records if r.full_name.value == "Bob Smith")
    assert len(bob.experience) == 1
    assert bob.experience[0].value.title == "Backend Engineer"
    assert bob.experience[0].value.company == "StartupXYZ"


def test_no_name_returns_empty(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_NO_NAME, encoding="utf-8")
    records = NotesSource().parse(str(f))
    assert records == []


def test_range_ye_takes_lower_bound(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_RANGE_YE, encoding="utf-8")
    records = NotesSource().parse(str(f))
    assert len(records) == 1
    assert records[0].years_experience.value == 3.0


def test_notes_prefix_name(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_NOTES_BLOCK, encoding="utf-8")
    records = NotesSource().parse(str(f))
    assert len(records) == 1
    assert records[0].full_name.value == "David Lee"


def test_notes_block_no_company_in_role(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_NOTES_BLOCK, encoding="utf-8")
    records = NotesSource().parse(str(f))
    exp = records[0].experience[0].value
    assert exp.title == "Junior Developer"
    assert exp.company is None  # not stated -- never guessed


def test_source_name_and_priority(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert r.source_name == "notes"
    assert r.source_priority == 1  # lowest of notes(1) < github(2) < crm(3)


def test_education_with_institution(tmp_path):
    text = "Candidate Bob Smith. Email: bob@example.com. Education: MS Computer Science, MIT, 2020."
    f = tmp_path / "n.txt"
    f.write_text(text, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert len(r.education) == 1
    edu = r.education[0].value
    assert edu.degree == "MS"
    assert edu.field == "Computer Science"
    assert edu.institution == "MIT"
    assert edu.end_year == 2020


def test_education_without_institution_stays_null(tmp_path):
    text = "Notes for David Lee. Education: BS Computer Science, 2022."
    f = tmp_path / "n.txt"
    f.write_text(text, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    edu = r.education[0].value
    assert edu.degree == "BS"
    assert edu.end_year == 2022
    assert edu.institution is None  # not stated -- never guessed


def test_method_tags_extracted_fields(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(_SINGLE, encoding="utf-8")
    r = NotesSource().parse(str(f))[0]
    assert r.full_name.method == "extracted"
    assert r.years_experience.method == "extracted"
