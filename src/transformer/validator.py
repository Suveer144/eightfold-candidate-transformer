from __future__ import annotations
from typing import Any

# Default canonical schema's expected Python types, matching the assignment's
# "Default output schema" table exactly. Used to validate the unmodified
# default output (no config).
DEFAULT_SCHEMA_TYPES: dict[str, Any] = {
    "candidate_id": str,
    "full_name": str,
    "emails": list,
    "phones": list,
    "location": dict,
    "links": dict,
    "headline": str,
    "years_experience": (int, float),
    "skills": list,
    "experience": list,
    "education": list,
    "provenance": list,
    "overall_confidence": (int, float),
}

# Config "type" string -> expected Python type(s), used to validate
# config-projected/reshaped output against the schema the caller requested.
_CONFIG_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "string[]": list,
    "number": (int, float),
    "number[]": list,
    "boolean": bool,
    "object": dict,
    "object[]": list,
}


def derive_schema_from_config(fields_config: list[dict]) -> dict[str, Any]:
    """Build an {output_path: expected_type} map from a config's "fields" array."""
    schema: dict[str, Any] = {}
    for field_def in fields_config:
        type_hint = field_def.get("type")
        if type_hint in _CONFIG_TYPE_MAP:
            schema[field_def["path"]] = _CONFIG_TYPE_MAP[type_hint]
    return schema


def validate_record(record: dict, expected_types: dict[str, Any]) -> list[str]:
    """
    Validate that `record`'s present, non-null fields match their expected
    Python type. Never raises -- returns a list of human-readable issues
    (empty = valid). Missing keys and null values are not issues here: a
    missing key may be intentional (config used on_missing="omit"), and
    nullability is governed separately by the schema's "type | null" notation.
    """
    issues: list[str] = []
    for key, expected in expected_types.items():
        if key not in record:
            continue
        value = record[key]
        if value is None:
            continue
        if not isinstance(value, expected):
            expected_name = (
                "/".join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__
            )
            issues.append(f"Field '{key}' expected type {expected_name}, got {type(value).__name__}")
    return issues
