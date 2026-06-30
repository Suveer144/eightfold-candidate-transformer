import pytest
from transformer.sources.crm import CRMSource

_CSV = """\
name,email,phone,city,region,country,skills,years_experience,current_company,title,education_institution,education_degree,education_field,education_year
Alice Johnson,alice@example.com,(415) 555-0101,San Francisco,CA,US,"Python,SQL",5,TechCorp,Data Scientist,UC Berkeley,BS,Computer Science,2019
"""

_CSV_NO_NAME = "name,email\n,nobody@example.com\n"


def test_csv_basic_parse(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    records = CRMSource().parse(str(f))
    assert len(records) == 1
    r = records[0]
    assert r.full_name.value == "Alice Johnson"
    assert r.source_name == "crm"


def test_csv_email(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert any(fv.value == "alice@example.com" for fv in r.emails)


def test_csv_phone_normalized(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert any(fv.normalized for fv in r.phones)
    assert any(fv.value == "+14155550101" for fv in r.phones)


def test_csv_skills(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    skill_values = [fv.value for fv in r.skills]
    assert "Python" in skill_values
    assert "SQL" in skill_values


def test_csv_years_experience(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert r.years_experience.value == 5.0


def test_csv_location(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert r.location.value.city == "San Francisco"
    assert r.location.value.region == "CA"
    assert r.location.value.country == "US"


def test_csv_experience(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert len(r.experience) == 1
    exp = r.experience[0].value
    assert exp.company == "TechCorp"
    assert exp.title == "Data Scientist"
    assert exp.start is None
    assert exp.end is None


def test_csv_education(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert len(r.education) == 1
    edu = r.education[0].value
    assert edu.institution == "UC Berkeley"
    assert edu.degree == "BS"
    assert edu.end_year == 2019


def test_csv_skips_nameless_rows(tmp_path):
    f = tmp_path / "crm.csv"
    f.write_text(_CSV_NO_NAME, encoding="utf-8")
    records = CRMSource().parse(str(f))
    assert records == []


def test_non_numeric_ye_ignored(tmp_path):
    csv = "name,email,years_experience\nTom Hanks,tom@test.com,unknown\n"
    f = tmp_path / "crm.csv"
    f.write_text(csv, encoding="utf-8")
    r = CRMSource().parse(str(f))[0]
    assert r.years_experience is None  # don't guess


def test_json_content_yields_no_records(tmp_path):
    # The assignment lists "Recruiter CSV export" and "ATS JSON blob" as two
    # alternative structured-source picks with different field-naming
    # conventions -- we picked CSV, so JSON parsing is out of scope. CRMSource
    # only reads CSV; JSON-shaped content has no matching "name" column and,
    # per the robustness constraint, degrades to zero records rather than
    # crashing or inventing data.
    f = tmp_path / "crm.json"
    f.write_text('[{"name": "Bob Smith", "email": "bob@example.com"}]', encoding="utf-8")
    records = CRMSource().parse(str(f))
    assert records == []
