from transformer.validator import validate_record, derive_schema_from_config, DEFAULT_SCHEMA_TYPES


def test_valid_default_record_no_issues():
    record = {
        "candidate_id": "C1",
        "full_name": "Alice",
        "emails": ["a@x.com"],
        "phones": [],
        "location": None,
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "headline": None,
        "years_experience": 5.0,
        "skills": [],
        "experience": [],
        "education": [],
        "provenance": [],
        "overall_confidence": 0.8,
    }
    assert validate_record(record, DEFAULT_SCHEMA_TYPES) == []


def test_type_mismatch_detected():
    record = {"emails": "not-a-list"}  # should be a list
    issues = validate_record(record, DEFAULT_SCHEMA_TYPES)
    assert len(issues) == 1
    assert "emails" in issues[0]


def test_missing_key_not_an_issue():
    # A key absent entirely (e.g. omitted by config) is not a validation issue
    record = {"full_name": "Alice"}
    assert validate_record(record, DEFAULT_SCHEMA_TYPES) == []


def test_null_value_not_an_issue():
    record = {"full_name": None, "years_experience": None}
    assert validate_record(record, DEFAULT_SCHEMA_TYPES) == []


def test_years_experience_accepts_int_or_float():
    assert validate_record({"years_experience": 5}, DEFAULT_SCHEMA_TYPES) == []
    assert validate_record({"years_experience": 5.5}, DEFAULT_SCHEMA_TYPES) == []
    assert validate_record({"years_experience": "5"}, DEFAULT_SCHEMA_TYPES) != []


def test_derive_schema_from_config():
    fields = [
        {"path": "full_name", "type": "string"},
        {"path": "skills", "type": "string[]"},
        {"path": "score", "type": "number"},
    ]
    schema = derive_schema_from_config(fields)
    assert schema["full_name"] is str
    assert schema["skills"] is list
    assert schema["score"] == (int, float)


def test_derived_schema_validates_projected_output():
    fields = [{"path": "primary_email", "type": "string"}]
    schema = derive_schema_from_config(fields)
    assert validate_record({"primary_email": "a@x.com"}, schema) == []
    assert validate_record({"primary_email": ["a@x.com"]}, schema) != []
