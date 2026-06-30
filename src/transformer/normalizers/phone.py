from __future__ import annotations
import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException


def normalize_phone(raw: str) -> tuple[str | None, str | None]:
    """
    Return (E.164 string, warning_or_None).
    On failure returns (None, warning) — never raises.
    Default region is US; handles international numbers that include country code.
    """
    if not raw or not raw.strip():
        return None, f"Empty phone value"
    try:
        parsed = phonenumbers.parse(raw, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164), None
        return None, f"Invalid phone number: {raw!r}"
    except NumberParseException as e:
        return None, f"Could not parse phone {raw!r}: {e}"
