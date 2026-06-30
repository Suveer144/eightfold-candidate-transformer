import pytest
from transformer.projector import resolve_path, apply_field_config

_RECORD = {
    "full_name": "Alice Johnson",
    "emails": ["alice@example.com", "alice.work@gmail.com"],
    "phones": ["415-555-0101"],
    "location": {"city": "San Francisco", "region": "CA", "country": "US"},
    "skills": [
        {"name": "Python", "confidence": 0.9, "sources": ["crm"]},
        {"name": "SQL", "confidence": 0.75, "sources": ["notes"]},
    ],
    "experience": [],
    "overall_confidence": 0.85,
}


# --- resolve_path ----------------------------------------------------------

def test_resolve_plain_field():
    assert resolve_path(_RECORD, "full_name") == "Alice Johnson"


def test_resolve_array_index():
    assert resolve_path(_RECORD, "emails[0]") == "alice@example.com"
    assert resolve_path(_RECORD, "emails[1]") == "alice.work@gmail.com"


def test_resolve_array_index_out_of_range():
    assert resolve_path(_RECORD, "emails[5]") is None


def test_resolve_dotted_path():
    assert resolve_path(_RECORD, "location.city") == "San Francisco"


def test_resolve_dotted_path_on_null_parent():
    record = dict(_RECORD, location=None)
    assert resolve_path(record, "location.city") is None


def test_resolve_flatten_map():
    assert resolve_path(_RECORD, "skills[].name") == ["Python", "SQL"]


def test_resolve_flatten_map_on_empty_list():
    assert resolve_path(_RECORD, "experience[].title") == []


def test_resolve_missing_field_returns_none():
    assert resolve_path(_RECORD, "nonexistent") is None


def test_resolve_malformed_segment_returns_none():
    assert resolve_path(_RECORD, "full_name[bad syntax") is None


# --- apply_field_config -----------------------------------------------------

def test_basic_remap():
    fields = [{"path": "primary_email", "from": "emails[0]", "type": "string"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    assert result == {"primary_email": "alice@example.com"}
    assert errors == []


def test_normalize_e164():
    fields = [{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    assert result["phone"] == "+14155550101"


def test_normalize_canonical_lowercases():
    fields = [{"path": "skill_names", "from": "skills[].name", "type": "string[]", "normalize": "canonical"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    assert result["skill_names"] == ["python", "sql"]


def test_missing_field_null_mode():
    fields = [{"path": "missing_thing", "from": "nope", "type": "string"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    assert result["missing_thing"] is None
    assert errors == []


def test_missing_field_omit_mode():
    fields = [{"path": "missing_thing", "from": "nope", "type": "string"}]
    result, errors = apply_field_config(_RECORD, fields, "omit")
    assert "missing_thing" not in result
    assert errors == []


def test_missing_required_field_error_mode():
    fields = [{"path": "missing_thing", "from": "nope", "type": "string", "required": True}]
    result, errors = apply_field_config(_RECORD, fields, "error")
    assert len(errors) == 1
    assert "missing_thing" in errors[0]


def test_missing_non_required_field_error_mode_does_not_error():
    fields = [{"path": "optional_thing", "from": "nope", "type": "string", "required": False}]
    result, errors = apply_field_config(_RECORD, fields, "error")
    assert errors == []
    assert result["optional_thing"] is None


def test_type_coercion_scalar_to_list():
    fields = [{"path": "name_list", "from": "full_name", "type": "string[]"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    assert result["name_list"] == ["Alice Johnson"]


def test_type_coercion_list_to_scalar():
    fields = [{"path": "first_skill_obj", "from": "skills", "type": "string"}]
    result, errors = apply_field_config(_RECORD, fields, "null")
    # skills is a list of dicts; coercing to scalar takes the first element
    assert result["first_skill_obj"] == _RECORD["skills"][0]
