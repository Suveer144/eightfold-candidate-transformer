from __future__ import annotations
import re
from typing import Any
from .schema import CanonicalProfile
from .normalizers.phone import normalize_phone
from .validator import DEFAULT_SCHEMA_TYPES, derive_schema_from_config, validate_record

_SEGMENT_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d*)\])?$")


class ProjectionError(Exception):
    """Raised internally when a required field is missing under on_missing='error'."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _resolve_segments(current: Any, segments: list[str]) -> Any:
    if not segments:
        return current
    if current is None:
        return None
    seg, *rest = segments
    m = _SEGMENT_RE.match(seg)
    if not m:
        return None  # malformed path segment -- treat as missing, never raise
    key, idx_part = m.group(1), m.group(2)
    if not isinstance(current, dict) or key not in current:
        return None
    value = current[key]
    if idx_part is None:
        return _resolve_segments(value, rest)
    if idx_part == "":
        # flatten-map: e.g. "skills[].name" -> apply remaining path to every item
        if not isinstance(value, list):
            return None
        if not rest:
            return value
        return [_resolve_segments(item, rest) for item in value]
    if not isinstance(value, list):
        return None
    i = int(idx_part)
    if i >= len(value) or i < -len(value):
        return None
    return _resolve_segments(value[i], rest)


def resolve_path(record: dict, path: str) -> Any:
    """
    Resolve a dotted/indexed path against a canonical record dict. Never raises.
    Examples: "full_name", "location.city", "emails[0]", "skills[].name"
    """
    return _resolve_segments(record, path.split("."))


def _normalize_phone_value(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    if v.startswith("+"):
        return v  # already E.164
    normalized, _ = normalize_phone(v)
    return normalized or v


def _apply_normalize(value: Any, directive: str | None) -> Any:
    if value is None or not directive:
        return value
    d = directive.strip().lower()
    if d == "e164":
        return [_normalize_phone_value(v) for v in value] if isinstance(value, list) else _normalize_phone_value(value)
    if d == "canonical":
        def canon(v):
            return v.strip().lower() if isinstance(v, str) else v
        return [canon(v) for v in value] if isinstance(value, list) else canon(value)
    return value


def _coerce_type(value: Any, type_hint: str | None) -> Any:
    if value is None or not type_hint:
        return value
    wants_list = type_hint.endswith("[]")
    if wants_list and not isinstance(value, list):
        return [value]
    if not wants_list and isinstance(value, list):
        return value[0] if value else None
    return value


def apply_field_config(record: dict, fields_config: list[dict], on_missing: str) -> tuple[dict, list[str]]:
    """
    Apply the "fields" array from a runtime config to a canonical record dict.
    Returns (projected_dict, errors). errors is non-empty only when a required
    field is missing under on_missing="error".
    """
    result: dict = {}
    errors: list[str] = []

    for field_def in fields_config:
        out_path = field_def["path"]
        from_path = field_def.get("from", out_path)
        type_hint = field_def.get("type")
        required = field_def.get("required", False)
        normalize_directive = field_def.get("normalize")

        value = resolve_path(record, from_path)
        value = _apply_normalize(value, normalize_directive)
        value = _coerce_type(value, type_hint)

        if value is None or value == [] or value == "":
            if required and on_missing == "error":
                errors.append(f"Required field '{out_path}' (from '{from_path}') is missing")
                continue
            if on_missing == "omit":
                continue
            # "null" (default) -- fall through and set null below
            value = None

        result[out_path] = value

    return result, errors


def project(profile: CanonicalProfile, config: dict | None) -> tuple[dict | None, list[str]]:
    """
    Apply a runtime config to a CanonicalProfile and return (output_dict, errors).
    output_dict is None only if the profile is filtered out by confidence_threshold.
    errors is non-empty when a required field is missing under on_missing="error", or
    when the projected output fails schema validation -- callers should route such
    records to an "invalid" bucket rather than discard them or return bad data silently.

    No config (config=None) -> full canonical schema as-is (the default output),
    still validated against the documented default schema before returning.
    """
    record = profile.to_dict()

    if not config:
        return record, validate_record(record, DEFAULT_SCHEMA_TYPES)

    include_low = config.get("include_low_confidence", True)
    threshold = float(config.get("confidence_threshold", 0.0))
    if not include_low and profile.overall_confidence < threshold:
        return None, []

    fields_config = config.get("fields")
    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", True)
    include_provenance = config.get("include_provenance", True)

    if fields_config:
        projected, errors = apply_field_config(record, fields_config, on_missing)
    else:
        projected, errors = dict(record), []

    if not include_confidence:
        projected.pop("overall_confidence", None)
    elif "overall_confidence" not in projected and fields_config:
        # fields list didn't explicitly include it, but the toggle wants it shown
        projected["overall_confidence"] = record["overall_confidence"]

    if not include_provenance:
        projected.pop("provenance", None)
    elif "provenance" not in projected and fields_config:
        projected["provenance"] = record["provenance"]

    # Validate the result against the requested schema (the config's own
    # field types when given, otherwise the default schema). Never crashes --
    # issues are surfaced as errors so the caller can route the record to
    # invalid_candidates rather than silently return mistyped data.
    schema = derive_schema_from_config(fields_config) if fields_config else DEFAULT_SCHEMA_TYPES
    errors = errors + validate_record(projected, schema)

    return projected, errors
