from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import hashlib


@dataclass
class Location:
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 alpha-2


@dataclass
class Links:
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.linkedin or self.github or self.portfolio or self.other)


@dataclass
class Skill:
    name: str
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)


@dataclass
class Experience:
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None    # YYYY-MM
    end: Optional[str] = None      # YYYY-MM, null if ongoing/unstated -- never assume "present"
    summary: Optional[str] = None


@dataclass
class Education:
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


@dataclass
class ProvenanceEntry:
    field: str
    source: str
    method: str  # "stated" | "extracted" | "inferred" | "normalized" | "supplied"


@dataclass
class FieldValue:
    """Single field value with source attribution and normalization metadata."""
    value: Any
    source: str
    priority: int
    raw: Any = None
    normalized: bool = False
    method: str = "stated"
    warnings: list = field(default_factory=list)


@dataclass
class RawRecord:
    """Output from a single source parser for one candidate."""
    source_name: str
    source_priority: int
    full_name: Optional[FieldValue] = None
    emails: list[FieldValue] = field(default_factory=list)
    phones: list[FieldValue] = field(default_factory=list)
    location: Optional[FieldValue] = None
    links: dict[str, FieldValue] = field(default_factory=dict)   # keys: linkedin/github/portfolio
    other_links: list[FieldValue] = field(default_factory=list)
    headline: Optional[FieldValue] = None
    skills: list[FieldValue] = field(default_factory=list)       # FieldValue.value is a skill name (str)
    years_experience: Optional[FieldValue] = None
    experience: list[FieldValue] = field(default_factory=list)   # FieldValue.value is an Experience
    education: list[FieldValue] = field(default_factory=list)    # FieldValue.value is an Education


@dataclass
class CanonicalProfile:
    """Merged, normalized, scored output profile -- matches the assignment's canonical schema table."""
    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    location: Optional[Location] = None
    links: Links = field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    provenance: list[ProvenanceEntry] = field(default_factory=list)
    overall_confidence: float = 0.0

    # Internal pipeline metadata -- NOT part of the canonical schema, never serialized
    warnings: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Full canonical record as a plain dict. Always includes provenance and
        overall_confidence -- they're part of the default schema, not opt-in.
        A runtime config may choose to strip or reshape them afterward."""
        return {
            "candidate_id": self.candidate_id,
            "full_name": self.full_name,
            "emails": self.emails,
            "phones": self.phones,
            "location": (
                {"city": self.location.city, "region": self.location.region, "country": self.location.country}
                if self.location else None
            ),
            "links": {
                "linkedin": self.links.linkedin,
                "github": self.links.github,
                "portfolio": self.links.portfolio,
                "other": self.links.other,
            },
            "headline": self.headline,
            "years_experience": self.years_experience,
            "skills": [
                {"name": s.name, "confidence": round(s.confidence, 3), "sources": s.sources}
                for s in self.skills
            ],
            "experience": [
                {"company": e.company, "title": e.title, "start": e.start, "end": e.end, "summary": e.summary}
                for e in self.experience
            ],
            "education": [
                {"institution": e.institution, "degree": e.degree, "field": e.field, "end_year": e.end_year}
                for e in self.education
            ],
            "provenance": [
                {"field": p.field, "source": p.source, "method": p.method} for p in self.provenance
            ],
            "overall_confidence": round(self.overall_confidence, 4),
        }


def make_candidate_id(email: Optional[str] = None, name: Optional[str] = None) -> str:
    key = (email or name or "unknown").lower().strip()
    return "C" + hashlib.sha256(key.encode()).hexdigest()[:12].upper()
