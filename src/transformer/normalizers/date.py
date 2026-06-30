from __future__ import annotations


def normalize_date(raw: str) -> tuple[str | None, str | None]:
    """Return (ISO 8601 date string YYYY-MM-DD, warning_or_None). Never raises."""
    if not raw or not raw.strip():
        return None, None
    try:
        from dateutil import parser as dateparser
        dt = dateparser.parse(raw.strip(), dayfirst=False)
        return dt.date().isoformat(), None
    except Exception as e:
        return None, f"Could not parse date {raw!r}: {e}"
