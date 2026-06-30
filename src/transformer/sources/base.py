from __future__ import annotations
from abc import ABC, abstractmethod
from ..schema import RawRecord

# Source priority — higher number wins scalar conflicts.
# Rationale:
#   notes  = lowest  — informal, ad-hoc, unverified recruiter shorthand
#   github = middle  — candidate self-maintained public profile; structured-ish
#                       but not independently verified and often sparse/stale
#   crm    = highest — recruiter-curated/verified system of record
SOURCE_PRIORITIES: dict[str, int] = {
    "notes": 1,
    "github": 2,
    "crm": 3,
}


class BaseSource(ABC):
    name: str

    def __init__(self) -> None:
        self.priority = SOURCE_PRIORITIES.get(self.name, 0)

    @abstractmethod
    def parse(self, path: str) -> list[RawRecord]:
        """Parse source file and return one RawRecord per candidate."""
        ...
