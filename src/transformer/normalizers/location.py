from __future__ import annotations
import re
import pycountry

_CACHE: dict[str, str | None] = {}

# A bare 2-letter uppercase code is ambiguous: it might be a US state
# ("CA" = California) or it might collide with an unrelated ISO 3166-1
# country code ("CA" = Canada). Only treat it as a US state when it's a
# genuine US state/territory abbreviation; otherwise keep it as the stated
# region and leave country unresolved rather than guessing. (Found via a
# real profile: "Manipal, KA" was wrongly resolving country=US, and
# "San Francisco, CA" was wrongly resolving country=Canada.)
US_STATE_CODES = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
})

# Hand-coded aliases for inputs pycountry misses
_ALIASES: dict[str, str] = {
    "us": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united states": "US", "united states of america": "US",
    "uk": "GB", "united kingdom": "GB", "england": "GB",
    "canada": "CA",
    "india": "IN",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "netherlands": "NL",
    "brazil": "BR",
    "mexico": "MX",
}


def normalize_location(raw: str) -> str | None:
    """Return ISO 3166-1 alpha-2 code, or None if unrecognized. Never raises."""
    if not raw or not raw.strip():
        return None
    key = raw.strip().lower()
    if key in _CACHE:
        return _CACHE[key]
    result = _ALIASES.get(key)
    if not result:
        try:
            result = pycountry.countries.lookup(raw.strip()).alpha_2
        except LookupError:
            result = None
    _CACHE[key] = result
    return result


def resolve_region_or_country(token: str) -> tuple[str | None, str | None]:
    """
    Resolve an ambiguous trailing location token into (region, country_iso2).
    See US_STATE_CODES docstring above for why bare 2-letter codes need
    special handling instead of a direct country lookup.
    """
    token = (token or "").strip()
    if not token:
        return None, None
    if re.fullmatch(r"[A-Z]{2}", token):
        if token in US_STATE_CODES:
            return token, "US"
        return token, None  # ambiguous -- keep region, don't assume country
    iso = normalize_location(token)
    if iso:
        return None, iso
    return token, None  # unrecognized -- keep as region, no country guess
