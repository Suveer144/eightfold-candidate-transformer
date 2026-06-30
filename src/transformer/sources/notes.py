from __future__ import annotations
import re
from pathlib import Path
from ..schema import FieldValue, RawRecord, Education, Location, Experience
from ..normalizers.phone import normalize_phone
from ..normalizers.location import resolve_region_or_country
from .base import BaseSource

# Candidate blocks are delimited by lines of dashes or equals signs
_BLOCK_SEP = re.compile(r"(?m)^[ \t]*(?:-{3,}|={3,})[ \t]*$")

# --- Name patterns (tried in order; first confident match wins) ----------
# IMPORTANT: use inline (?i:...) only on the verb prefix so that [A-Z] in the
# name capture group stays case-sensitive — prevents "today" / "today" etc.
# from being absorbed into the name.
_NAME_PATS = [
    re.compile(r"(?i:spoke\s+with|met\s+with|called|interviewed|spoke\s+to)\s+([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})"),
    re.compile(r"(?i:Candidate|Name)[:\s]+([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})"),
    re.compile(r"(?i:Notes\s+for\s+)([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})"),
    re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})\b", re.MULTILINE),
]

# --- Email -----------------------------------------------------------------
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.]+")

# --- Phone -------------------------------------------------------------
# Two alternatives, tried left to right:
#   1. International, explicit "+" and country code (e.g. +91-7414872335) --
#      country code can be 1-3 digits, unlike the old pattern which only
#      handled a single-digit "1" (US/Canada) and silently mangled others.
#   2. Bare US-style grouping (e.g. (415) 555-0101, 408-555-0201).
# group(0) (the whole match) is passed to normalize_phone(), which lets
# phonenumbers.parse() read the explicit "+" country code itself.
_PHONE_RE = re.compile(
    r"\+\d{1,3}[-.\s]?\d{2,5}[-.\s]?\d{2,5}[-.\s]?\d{0,4}\b"
    r"|\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# --- Years of experience (lower bound rule for ranges) --------------------
# Range pattern MUST come first so "3-5 years" → 3.0, not 5.0.
_YE_PATS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*\d+\s*years?\s+(?:of\s+)?(?:experience|exp\.?)\b", re.I),  # range → lower bound
    re.compile(r"(?:over|about|approximately)?\s*(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?(?:total\s+)?(?:professional\s+)?(?:experience|exp\.?)\b", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\+?\s*yrs?\s*(?:of\s+)?(?:experience|exp\.?)\b", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\+?\s*years?\s+exp\b", re.I),
]

# --- Current role (-> one Experience entry; title + optional company) -----
# Only the CURRENT role is extracted -- notes prose rarely states clean
# start/end dates for past roles, and guessing them would violate the
# never-assume rule. Past roles mentioned in free text are a deliberate
# scope limitation (see design doc).
_ROLE_PATS = [
    re.compile(r"Currently:\s*(.+?)(?:\s+at\s+([A-Za-z0-9&.\- ]+?))?(?:\s*[,.\n]|$)", re.I),
    re.compile(r"currently\s+(?:working\s+as\s+)?(?:an?\s+)?(.+?)(?:\s+at\s+([A-Za-z0-9&.\- ]+?))?(?:\s*[,.\n]|$)", re.I),
    re.compile(r"works?\s+as\s+(?:an?\s+)?(.+?)(?:\s+at\s+([A-Za-z0-9&.\- ]+?))?(?:\s*[,.\n]|$)", re.I),
    re.compile(r"(?:title|role|position)[:\s]+(.+?)(?:\s+at\s+([A-Za-z0-9&.\- ]+?))?(?:\s*[,.\n]|$)", re.I),
]

# --- Location -------------------------------------------------------------
# Ambiguous trailing tokens (bare 2-letter codes etc.) are resolved via
# resolve_region_or_country() -- see normalizers/location.py for why this
# can't be a direct country lookup.
_LOC_PATS = [
    re.compile(r"(?:based\s+in|located\s+in|lives?\s+in|resides?\s+in)\s+([A-Za-z .]+?),\s*([A-Z]{2}|[A-Za-z ]+?)(?:\s*[.\n,]|$)", re.I),
    re.compile(r"Location[:\s]+([A-Za-z .]+?),\s*([A-Z]{2}|[A-Za-z ]+?)(?:\s*[.\n,]|$)", re.I),
    re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s*([A-Z]{2})\b"),  # "San Jose, CA"
]

# --- Skills ---------------------------------------------------------------
_SKILL_PATS = [
    re.compile(r"[Ss]kills?\s*(?:include)?[:\s]+(.+?)(?:[.\n]|$)"),
    re.compile(r"background\s+in\s+(.+?)(?:[.\n]|$)", re.I),
    re.compile(r"experience\s+(?:with|in)\s+(.+?)(?:[.\n]|$)", re.I),
    re.compile(r"(?:strong\s+)?(?:knowledge|expertise)\s+(?:of|in)\s+(.+?)(?:[.\n]|$)", re.I),
    re.compile(r"(?:proficient|skilled)\s+in\s+(.+?)(?:[.\n]|$)", re.I),
    # NOTE: do NOT add a bare "mentioned (.+?)" pattern here -- it overlaps
    # with the "experience with X" pattern above and captures the leading
    # "experience with" wording as part of the skill text (e.g. produces
    # "experience with LangChain" instead of "LangChain"). The pattern above
    # already matches "mentioned experience with X" on its own.
]

# --- Education (-> degree, field, institution, end_year) ------------------
# Separator before the institution is either a comma or "from"/"at"; the
# institution group is optional since notes sometimes omit the school
# entirely (e.g. "BS Computer Science, 2022" with no institution stated --
# left null rather than guessed).
_EDU_RE = re.compile(
    r"(B\.?S\.?|M\.?S\.?|Ph\.?D\.?|B\.?A\.?|M\.?A\.?|MBA|B\.?E\.?|M\.?E\.?|B\.?Tech\.?|M\.?Tech\.?|Bachelor'?s?|Master'?s?|Doctorate)"
    r"\s+(?:of\s+|in\s+|degree\s+in\s+)?([A-Za-z ]{2,40}?)"
    r"(?:\s*,\s*|\s+from\s+|\s+at\s+)([A-Za-z .]{2,60}?)?"
    r"(?:[\s,]\s*(\d{4}))?"
    r"(?:[.,\n]|$)",
    re.I,
)


def _split_skill_text(text: str) -> list[str]:
    parts = re.split(r",\s*|\s+and\s+", text)
    return [p.strip() for p in parts if 1 < len(p.strip()) <= 50]


class NotesSource(BaseSource):
    """Parses free-text recruiter notes. Blocks separated by --- or === lines."""
    name = "notes"

    def parse(self, path: str) -> list[RawRecord]:
        text = Path(path).read_text(encoding="utf-8")
        blocks = _BLOCK_SEP.split(text)
        blocks = [b.strip() for b in blocks if b.strip()]
        if not blocks:
            return []
        return [r for r in (_parse_block(b, self.name, self.priority) for b in blocks) if r]


def _parse_block(text: str, source: str, priority: int) -> RawRecord | None:
    def fv(value, raw=None, method="extracted", **kw) -> FieldValue:
        return FieldValue(value=value, source=source, priority=priority, raw=raw or value, method=method, **kw)

    rec = RawRecord(source_name=source, source_priority=priority)

    # Name
    for pat in _NAME_PATS:
        m = pat.search(text)
        if m:
            full_name = m.group(1).strip()
            if len(full_name.split()) >= 2:
                rec.full_name = fv(full_name)
                break
    if not rec.full_name:
        return None  # can't do anything useful without a name

    # Emails
    seen_emails: set[str] = set()
    for m in _EMAIL_RE.finditer(text):
        # Strip trailing punctuation the regex may absorb (e.g. "email@x.com.")
        e = m.group(0).lower().rstrip(".,;:)")
        if e not in seen_emails and "@" in e:
            seen_emails.add(e)
            rec.emails.append(fv(e))

    # Phones
    seen_phones: set[str] = set()
    for m in _PHONE_RE.finditer(text):
        raw_p = m.group(0).strip()
        if raw_p in seen_phones:
            continue
        seen_phones.add(raw_p)
        normalized, warn = normalize_phone(raw_p)
        rec.phones.append(FieldValue(
            value=normalized if normalized else raw_p,
            source=source, priority=priority, raw=raw_p,
            normalized=normalized is not None,
            method="normalized" if normalized else "extracted",
            warnings=[warn] if warn else [],
        ))

    # Years experience — take first match, use lower bound for ranges
    for pat in _YE_PATS:
        m = pat.search(text)
        if m:
            try:
                val = float(m.group(1))
                rec.years_experience = FieldValue(
                    value=val, source=source, priority=priority,
                    raw=m.group(0).strip(), normalized=True, method="extracted",
                )
                break
            except (ValueError, IndexError):
                pass

    # Current role -> one Experience entry
    for pat in _ROLE_PATS:
        m = pat.search(text)
        if m:
            title = m.group(1).strip().rstrip(".,")
            company = m.group(2).strip().rstrip(".,") if m.group(2) else None
            if 2 < len(title) < 80:
                exp = Experience(company=company, title=title, start=None, end=None, summary=None)
                rec.experience.append(fv(exp, raw=m.group(0).strip()))
                break

    # Location
    for pat in _LOC_PATS:
        m = pat.search(text)
        if m:
            city = m.group(1).strip()
            region_or_country = m.group(2).strip()
            region, country_iso = resolve_region_or_country(region_or_country)
            loc = Location(city=city, region=region, country=country_iso)
            rec.location = fv(loc, raw=m.group(0).strip())
            break

    # Skills — union across all skill patterns
    seen_skills: set[str] = set()
    for pat in _SKILL_PATS:
        m = pat.search(text)
        if m:
            for skill in _split_skill_text(m.group(1)):
                key = skill.lower()
                if key not in seen_skills:
                    seen_skills.add(key)
                    rec.skills.append(fv(skill))

    # Education
    for m in _EDU_RE.finditer(text):
        degree = m.group(1).strip()
        edu_field = m.group(2).strip()
        institution = m.group(3).strip() if m.group(3) else None
        year: int | None = None
        if m.group(4):
            try:
                year = int(m.group(4))
            except ValueError:
                pass
        edu = Education(institution=institution, degree=degree or None, field=edu_field or None, end_year=year)
        rec.education.append(fv(edu, raw=m.group(0).strip()))

    return rec
