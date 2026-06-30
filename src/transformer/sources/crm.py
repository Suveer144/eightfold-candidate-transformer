from __future__ import annotations
import csv
from pathlib import Path
from ..schema import FieldValue, RawRecord, Education, Location, Experience
from ..normalizers.phone import normalize_phone
from ..normalizers.location import normalize_location
from .base import BaseSource


class CRMSource(BaseSource):
    """
    Parses a recruiter CRM export. CSV only -- the assignment lists "Recruiter
    CSV export" and "ATS JSON blob" as two alternative structured-source picks
    with different field-naming conventions; we picked CSV, so JSON parsing is
    intentionally out of scope here.

    Expected columns (extras tolerated and used if present, per "heuristic
    extraction is fine"): name, email, phone, current_company, title, city,
    region, country, skills, years_experience, education_institution,
    education_degree, education_field, education_year.
    """
    name = "crm"

    def parse(self, path: str) -> list[RawRecord]:
        records = []
        with open(Path(path), newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = self._row_to_record({k.strip(): (v or "").strip() for k, v in row.items()})
                if rec:
                    records.append(rec)
        return records

    def _row_to_record(self, row: dict) -> RawRecord | None:
        def fv(val: str | None, **kw) -> FieldValue | None:
            v = (val or "").strip()
            return FieldValue(value=v, source=self.name, priority=self.priority, raw=v, method="stated", **kw) if v else None

        rec = RawRecord(source_name=self.name, source_priority=self.priority)

        raw_name = row.get("name") or row.get("full_name") or row.get("candidate_name") or ""
        rec.full_name = fv(raw_name)
        if not rec.full_name:
            return None  # name is the only identity anchor a CRM row has -- skip if absent

        for key in ("email", "email_address", "emails"):
            for e in (row.get(key) or "").split(";"):
                e = e.strip().lower()
                if e and "@" in e:
                    rec.emails.append(FieldValue(value=e, source=self.name, priority=self.priority, raw=e, method="stated"))

        for key in ("phone", "phone_number", "mobile", "cell"):
            raw_p = (row.get(key) or "").strip()
            if raw_p:
                normalized, warn = normalize_phone(raw_p)
                rec.phones.append(FieldValue(
                    value=normalized if normalized else raw_p,
                    source=self.name, priority=self.priority, raw=raw_p,
                    normalized=normalized is not None,
                    method="normalized" if normalized else "stated",
                    warnings=[warn] if warn else [],
                ))

        city = (row.get("city") or "").strip() or None
        region = (row.get("region") or row.get("state") or "").strip() or None
        country_raw = (row.get("country") or "US").strip()
        country_iso = normalize_location(country_raw) or (country_raw if len(country_raw) == 2 else None)
        if city or region or country_iso:
            loc = Location(city=city, region=region, country=country_iso)
            rec.location = FieldValue(value=loc, source=self.name, priority=self.priority, raw=country_raw, method="normalized")

        for s in (row.get("skills") or row.get("skill_set") or "").split(","):
            s = s.strip()
            if s:
                rec.skills.append(FieldValue(value=s, source=self.name, priority=self.priority, raw=s, method="stated"))

        ye_raw = (row.get("years_experience") or row.get("experience_years") or "").strip()
        if ye_raw:
            try:
                rec.years_experience = FieldValue(
                    value=float(ye_raw), source=self.name, priority=self.priority, raw=ye_raw,
                    normalized=True, method="stated",
                )
            except ValueError:
                pass  # non-numeric -- leave null, don't guess

        # current_company + title -> a single experience entry (CRM exports
        # typically don't carry start/end dates for the current role)
        company = (row.get("current_company") or row.get("company") or "").strip()
        title = (row.get("title") or row.get("current_role") or row.get("job_title") or "").strip()
        if company or title:
            exp = Experience(company=company or None, title=title or None, start=None, end=None, summary=None)
            rec.experience.append(FieldValue(value=exp, source=self.name, priority=self.priority, raw=f"{title}@{company}", method="stated"))

        institution = (row.get("education_institution") or row.get("school") or "").strip()
        degree = (row.get("education_degree") or row.get("degree") or "").strip()
        edu_field = (row.get("education_field") or row.get("major") or "").strip()
        edu_year_raw = (row.get("education_year") or row.get("education_end_year") or row.get("graduation_year") or "").strip()
        edu_year: int | None = None
        if edu_year_raw:
            try:
                edu_year = int(edu_year_raw)
            except ValueError:
                pass
        if institution or degree or edu_field:
            edu = Education(institution=institution or None, degree=degree or None, field=edu_field or None, end_year=edu_year)
            rec.education.append(FieldValue(value=edu, source=self.name, priority=self.priority, raw=edu_year_raw, method="stated"))

        return rec
