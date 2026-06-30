from __future__ import annotations
from .schema import (
    CanonicalProfile, FieldValue, RawRecord, Links, Skill, Experience, Education,
    ProvenanceEntry, make_candidate_id,
)
from .normalizers.skill import canonicalize_skill

# Base confidence by extraction method -- used for per-skill confidence.
# Higher = more directly asserted by a human/system; lower = inferred indirectly.
_METHOD_BASE_CONFIDENCE = {
    "stated": 0.9,       # direct field from a structured/semi-structured source
    "normalized": 0.85,  # stated value that also passed a normalizer
    "extracted": 0.75,   # heuristically parsed out of free text
    "supplied": 0.6,     # externally supplied by the caller (e.g. ?email= binding)
    "inferred": 0.5,     # indirect evidence, not a direct claim (e.g. repo language)
}
_SKILL_SOURCE_BOOST = 0.1  # per additional distinct corroborating source, capped at 1.0


def _norm_email(e: str) -> str:
    return e.lower().strip()

def _norm_name(n: str | None) -> str:
    return " ".join((n or "").lower().split())


def group_records(all_records: list[RawRecord]) -> list[list[RawRecord]]:
    """
    Group RawRecords that belong to the same candidate.
    Primary key: any shared email address.
    Fallback key: exact normalized full_name match.
    Records that share nothing form their own group.
    """
    groups: list[list[RawRecord]] = []
    email_to_group: dict[str, int] = {}
    name_to_group: dict[str, int] = {}

    for rec in all_records:
        emails = {_norm_email(fv.value) for fv in rec.emails}
        name_key = _norm_name(rec.full_name.value if rec.full_name else None)

        matched: int | None = None
        for e in emails:
            if e in email_to_group:
                matched = email_to_group[e]
                break
        if matched is None and name_key and name_key in name_to_group:
            matched = name_to_group[name_key]

        if matched is not None:
            groups[matched].append(rec)
            for e in emails:
                email_to_group.setdefault(e, matched)
        else:
            idx = len(groups)
            groups.append([rec])
            for e in emails:
                email_to_group[e] = idx
            if name_key:
                name_to_group[name_key] = idx

    return groups


def merge_group(records: list[RawRecord]) -> CanonicalProfile:
    """
    Merge a candidate group into a single CanonicalProfile.
    Scalar fields: highest-priority source wins (ties go to last-encountered).
    List fields: union across all sources, deduplicated by normalised key.
    """
    records = sorted(records, key=lambda r: r.source_priority)
    conflicts: list[dict] = []
    warnings: list[str] = []
    provenance: list[ProvenanceEntry] = []
    seen_provenance: set[tuple] = set()

    def _add_provenance(field_name: str, fv: FieldValue) -> None:
        key = (field_name, fv.source, fv.method)
        if key not in seen_provenance:
            seen_provenance.add(key)
            provenance.append(ProvenanceEntry(field=field_name, source=fv.source, method=fv.method))

    def _merge_scalar(field_name: str) -> FieldValue | None:
        values = [getattr(r, field_name) for r in records if getattr(r, field_name) is not None]
        if not values:
            return None
        winner = max(values, key=lambda fv: fv.priority)
        losers = [fv for fv in values if fv is not winner and str(fv.value) != str(winner.value)]
        if losers:
            conflicts.append({
                "field": field_name,
                "winner": {"source": winner.source, "value": str(winner.value)},
                "losers": [{"source": fv.source, "value": str(fv.value)} for fv in losers],
            })
        _add_provenance(field_name, winner)
        warnings.extend(winner.warnings)
        return winner

    def _merge_list(field_name: str, key_fn=None) -> list[FieldValue]:
        seen: set[str] = set()
        result: list[FieldValue] = []
        for rec in records:
            for fv in getattr(rec, field_name):
                key = key_fn(fv.value) if key_fn else str(fv.value).lower().strip()
                if key not in seen:
                    seen.add(key)
                    result.append(fv)
                    warnings.extend(fv.warnings)
                _add_provenance(field_name, fv)
        return result

    full_name_fv = _merge_scalar("full_name")
    loc_fv = _merge_scalar("location")
    ye_fv = _merge_scalar("years_experience")
    headline_fv = _merge_scalar("headline")

    email_fvs = _merge_list("emails", key_fn=_norm_email)
    phone_fvs = _merge_list("phones", key_fn=lambda v: v)  # already E.164 or raw

    # --- Skills: group by CANONICALIZED name so aliases like "nodejs" and
    # "node.js" converge on one group, combine confidence + sources. The
    # schema's "canonical skill names" note applies to the default output --
    # this isn't just an opt-in config normalize directive. -----------------
    skill_groups: dict[str, list[FieldValue]] = {}
    skill_order: list[str] = []
    for rec in records:
        for fv in rec.skills:
            key = canonicalize_skill(fv.value).lower()
            if key not in skill_groups:
                skill_groups[key] = []
                skill_order.append(key)
            skill_groups[key].append(fv)
            _add_provenance("skills", fv)
            warnings.extend(fv.warnings)

    skills: list[Skill] = []
    for key in skill_order:
        fvs = skill_groups[key]
        base = max(_METHOD_BASE_CONFIDENCE.get(fv.method, 0.5) for fv in fvs)
        distinct_sources = sorted({fv.source for fv in fvs})
        confidence = min(1.0, base + _SKILL_SOURCE_BOOST * (len(distinct_sources) - 1))
        # Canonicalize from whichever source has the highest base confidence,
        # so a deliberately-cased acronym (e.g. "RAG") isn't lost to a lower-
        # confidence lowercase variant.
        best_raw = max(fvs, key=lambda f: _METHOD_BASE_CONFIDENCE.get(f.method, 0.5)).value
        skills.append(Skill(name=canonicalize_skill(best_raw), confidence=round(confidence, 3), sources=distinct_sources))

    # --- Experience: dedup by normalized company only (a company match is a
    # strong same-job signal even when sources phrase the title differently;
    # title itself is then resolved like any other scalar, highest-priority
    # source wins, with a conflict logged if sources disagree) -------------
    exp_groups: dict[str, list[FieldValue]] = {}
    exp_order: list[str] = []
    for rec in records:
        for fv in rec.experience:
            e = fv.value
            key = (e.company or "").strip().lower() or f"__no_company_{id(fv)}"  # untitled/company-less entries stay distinct
            if key not in exp_groups:
                exp_groups[key] = []
                exp_order.append(key)
            exp_groups[key].append(fv)
            _add_provenance("experience", fv)
            warnings.extend(fv.warnings)

    experience: list[Experience] = []
    for key in exp_order:
        fvs = exp_groups[key]
        fvs_sorted = sorted(fvs, key=lambda f: f.priority)  # low -> high priority
        merged = Experience()
        for f in fvs_sorted:  # higher priority overwrites lower as we go
            e = f.value
            merged.company = e.company or merged.company
            merged.start = e.start or merged.start
            merged.end = e.end or merged.end
            merged.summary = e.summary or merged.summary

        titles = [(f.value.title, f) for f in fvs if f.value.title]
        if titles:
            winner_title, winner_fv = max(titles, key=lambda t: t[1].priority)
            merged.title = winner_title
            distinct_titles = {t for t, _ in titles}
            if len(distinct_titles) > 1:
                conflicts.append({
                    "field": "experience.title",
                    "winner": {"source": winner_fv.source, "value": winner_title},
                    "losers": [
                        {"source": f.source, "value": t} for t, f in titles if t != winner_title
                    ],
                })
        experience.append(merged)

    # --- Education: dedup by normalized (institution, degree), fill gaps
    # across sources rather than keeping only the first-seen entry. (Bug:
    # _merge_list's plain "first one wins" dedup discarded CRM's stated
    # end_year=2027 because notes -- processed first, lowest priority --
    # claimed the same (institution, degree) key with no year stated.) -----
    edu_groups: dict[str, list[FieldValue]] = {}
    edu_order: list[str] = []
    for rec in records:
        for fv in rec.education:
            e = fv.value
            key = f"{(e.institution or '').strip().lower()}|{(e.degree or '').strip().lower()}"
            if key not in edu_groups:
                edu_groups[key] = []
                edu_order.append(key)
            edu_groups[key].append(fv)
            _add_provenance("education", fv)
            warnings.extend(fv.warnings)

    education: list[Education] = []
    for key in edu_order:
        fvs_sorted = sorted(edu_groups[key], key=lambda f: f.priority)  # low -> high priority
        merged_edu = Education()
        for f in fvs_sorted:  # higher priority overwrites lower as we go
            e = f.value
            merged_edu.institution = e.institution or merged_edu.institution
            merged_edu.degree = e.degree or merged_edu.degree
            merged_edu.field = e.field or merged_edu.field
            merged_edu.end_year = e.end_year or merged_edu.end_year
        education.append(merged_edu)

    # --- Links: per-sub-field priority merge, "other" unioned --------------
    links = Links()
    for sub in ("linkedin", "github", "portfolio"):
        candidates = [rec.links[sub] for rec in records if sub in rec.links]
        if candidates:
            winner = max(candidates, key=lambda fv: fv.priority)
            losers = [fv for fv in candidates if fv is not winner and fv.value != winner.value]
            if losers:
                conflicts.append({
                    "field": f"links.{sub}",
                    "winner": {"source": winner.source, "value": winner.value},
                    "losers": [{"source": fv.source, "value": fv.value} for fv in losers],
                })
            setattr(links, sub, winner.value)
            _add_provenance(f"links.{sub}", winner)

    other_seen: set[str] = set()
    for rec in records:
        for fv in rec.other_links:
            if fv.value not in other_seen:
                other_seen.add(fv.value)
                links.other.append(fv.value)
                _add_provenance("links.other", fv)

    primary_email = email_fvs[0].value if email_fvs else None
    primary_name = full_name_fv.value if full_name_fv else None

    return CanonicalProfile(
        candidate_id=make_candidate_id(primary_email, primary_name),
        full_name=full_name_fv.value if full_name_fv else None,
        emails=[fv.value for fv in email_fvs],
        phones=[fv.value for fv in phone_fvs],
        location=loc_fv.value if loc_fv else None,
        links=links,
        headline=headline_fv.value if headline_fv else None,
        years_experience=ye_fv.value if ye_fv else None,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        warnings=warnings,
        conflicts=conflicts,
    )
