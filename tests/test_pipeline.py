import json
import pytest
from transformer.pipeline import run_pipeline

_CSV = """\
name,email,phone,city,region,country,skills,years_experience,current_company,title
Alice Johnson,alice@example.com,(415) 555-0101,San Francisco,CA,US,"Python,SQL",5,TechCorp,Data Scientist
"""

_NOTES = """\
Spoke with Alice Johnson today. Email: alice@example.com.
Based in San Francisco, CA. Currently a Senior Data Scientist. 7 years of experience.
Skills: Python, Machine Learning.
"""

_NOTES_NEW = """\
Notes for David Lee. Phone: 408-555-0201. Lives in San Jose, CA.
Experience with Django, REST APIs. About 2 years of experience.
Currently a Junior Developer.
"""


def test_basic_run(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    notes_f = tmp_path / "notes.txt"
    notes_f.write_text(_NOTES)
    result = run_pipeline([("crm", str(csv_f)), ("notes", str(notes_f))])
    assert result["meta"]["total_candidates"] == 1
    c = result["candidates"][0]
    assert c["full_name"] == "Alice Johnson"
    assert "alice@example.com" in c["emails"]
    assert c["overall_confidence"] > 0.5


def test_no_config_returns_full_canonical_schema(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    result = run_pipeline([("crm", str(csv_f))])
    c = result["candidates"][0]
    for key in ("candidate_id", "full_name", "emails", "phones", "location", "links",
                "headline", "years_experience", "skills", "experience", "education",
                "provenance", "overall_confidence"):
        assert key in c


def test_crm_wins_ye_conflict(tmp_path):
    # CRM says 5 years, notes says 7 years → CRM wins (priority 3 > 1)
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    notes_f = tmp_path / "notes.txt"
    notes_f.write_text(_NOTES)
    result = run_pipeline([("crm", str(csv_f)), ("notes", str(notes_f))])
    assert result["candidates"][0]["years_experience"] == 5.0


def test_new_candidate_from_notes_only(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    notes_f = tmp_path / "notes.txt"
    notes_f.write_text(_NOTES + "\n---\n" + _NOTES_NEW)
    result = run_pipeline([("crm", str(csv_f)), ("notes", str(notes_f))])
    assert result["meta"]["total_candidates"] == 2


def test_config_field_reshape_rename_and_normalize(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    cfg_f = tmp_path / "cfg.json"
    cfg_f.write_text(json.dumps({
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
            {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
            {"path": "skill_list", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
        ],
        "include_confidence": True,
        "on_missing": "null",
    }))
    result = run_pipeline([("crm", str(csv_f))], config_path=str(cfg_f))
    c = result["candidates"][0]
    assert c["full_name"] == "Alice Johnson"
    assert c["primary_email"] == "alice@example.com"
    assert c["phone"] == "+14155550101"
    assert "python" in c["skill_list"]  # canonical = lowercased
    assert "name" not in c
    assert "emails" not in c


def test_config_on_missing_omit(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text("name,email\nNo Phone Guy,nophone@example.com\n")
    cfg_f = tmp_path / "cfg.json"
    cfg_f.write_text(json.dumps({
        "fields": [
            {"path": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
        ],
        "on_missing": "omit",
    }))
    result = run_pipeline([("crm", str(csv_f))], config_path=str(cfg_f))
    c = result["candidates"][0]
    assert "phone" not in c  # omitted, not null


def test_config_on_missing_error_routes_to_invalid(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text("name,email\nNo Phone Guy,nophone@example.com\n")
    cfg_f = tmp_path / "cfg.json"
    cfg_f.write_text(json.dumps({
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "phone", "from": "phones[0]", "type": "string", "required": True},
        ],
        "on_missing": "error",
    }))
    result = run_pipeline([("crm", str(csv_f))], config_path=str(cfg_f))
    assert result["meta"]["total_candidates"] == 0
    assert result["meta"]["invalid_candidate_count"] == 1
    assert "phone" in result["invalid_candidates"][0]["errors"][0]


def test_config_include_provenance_false(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    cfg_f = tmp_path / "cfg.json"
    cfg_f.write_text(json.dumps({"include_provenance": False}))
    result = run_pipeline([("crm", str(csv_f))], config_path=str(cfg_f))
    assert "provenance" not in result["candidates"][0]


def test_config_include_confidence_false(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    cfg_f = tmp_path / "cfg.json"
    cfg_f.write_text(json.dumps({"include_confidence": False}))
    result = run_pipeline([("crm", str(csv_f))], config_path=str(cfg_f))
    assert "overall_confidence" not in result["candidates"][0]


def test_unknown_source_raises(tmp_path):
    with pytest.raises(ValueError, match="Unknown source type"):
        run_pipeline([("badtype", "somefile.txt")])


def test_meta_fields(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    result = run_pipeline([("crm", str(csv_f))])
    assert "processed_at" in result["meta"]
    assert "crm" in result["meta"]["sources_used"]
    assert result["meta"]["total_candidates"] >= 1


def test_deterministic_output(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    r1 = run_pipeline([("crm", str(csv_f))])
    r2 = run_pipeline([("crm", str(csv_f))])
    assert r1["candidates"][0]["candidate_id"] == r2["candidates"][0]["candidate_id"]
    assert r1["candidates"][0]["full_name"] == r2["candidates"][0]["full_name"]


# --- three-source integration (crm + notes + github) ------------------------

_GITHUB_SNAPSHOT = {
    "profile": {"login": "alicedev", "name": None, "company": None, "location": None},
    "repos": [
        {"name": "ml-toolkit", "language": "Python", "fork": False},
        {"name": "infra", "language": "Go", "fork": False},
    ],
}


def test_three_source_merge_with_github_binding(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    notes_f = tmp_path / "notes.txt"
    notes_f.write_text(_NOTES)
    gh_f = tmp_path / "gh.json"
    gh_f.write_text(json.dumps(_GITHUB_SNAPSHOT))

    result = run_pipeline([
        ("crm", str(csv_f)),
        ("notes", str(notes_f)),
        ("github", f"{gh_f}?email=alice@example.com"),
    ])

    assert result["meta"]["total_candidates"] == 1
    c = result["candidates"][0]
    assert c["full_name"] == "Alice Johnson"
    assert "alice@example.com" in c["emails"]
    skill_names = {s["name"] for s in c["skills"]}
    assert "Go" in skill_names
    assert "Python" in skill_names
    assert "Machine Learning" in skill_names
    assert "github" in result["meta"]["sources_used"]


def test_github_without_binding_stays_separate(tmp_path):
    csv_f = tmp_path / "crm.csv"
    csv_f.write_text(_CSV)
    gh_f = tmp_path / "gh.json"
    gh_f.write_text(json.dumps(_GITHUB_SNAPSHOT))

    result = run_pipeline([("crm", str(csv_f)), ("github", str(gh_f))])
    assert result["meta"]["total_candidates"] == 2
