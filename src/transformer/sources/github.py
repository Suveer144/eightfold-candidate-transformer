from __future__ import annotations
import json
import re
from pathlib import Path
from ..schema import FieldValue, RawRecord, Location, Experience
from ..normalizers.location import resolve_region_or_country
from .base import BaseSource

_API_BASE = "https://api.github.com"
_TIMEOUT_SECONDS = 10

_USERNAME_FROM_URL = re.compile(r"github\.com/([A-Za-z0-9\-]+)/?", re.I)


def _extract_username(raw: str) -> str:
    m = _USERNAME_FROM_URL.search(raw)
    return m.group(1) if m else raw.strip().lstrip("@")


class GitHubSource(BaseSource):
    """
    Parses a public GitHub profile into a RawRecord.

    `path` accepts one of:
      - a GitHub username                       e.g. "Suveer144"
      - a GitHub profile URL                     e.g. "https://github.com/Suveer144"
      - a path to a local JSON snapshot file      e.g. "data/samples/github_snapshot.json"
        (shaped as {"profile": {...}, "repos": [...]}, matching the raw GitHub API
        responses -- used for deterministic/offline runs and tests, no network call)

    Optional identity binding: append "?email=<address>" to explicitly state which
    candidate this profile belongs to. GitHub's public API exposes no phone and
    rarely exposes email or name, so without this hint a profile can't be linked
    to records from other sources. This is a STATED fact supplied by the caller,
    not a guess -- consistent with the "never assume" merge policy.

      --source "github:Suveer144?email=suveer.agarwala@gmail.com"

    Field mapping:
      name            -> full_name
      location        -> location (city/region/country resolved, never guessed)
      html_url        -> links.github
      blog            -> links.portfolio (if set)
      bio             -> headline
      company         -> experience[0].title=null, company=<company> (weak signal,
                         no title available from the API)
      repo languages  -> skills, excluding forks (not original work); method="inferred",
                         confidence lower than a stated skill -- evidence of usage,
                         not a self-reported claim.

    Network/API failures (404, rate limit, timeout, malformed response) degrade
    gracefully to an empty result. This source never raises.
    """
    name = "github"

    def parse(self, path: str) -> list[RawRecord]:
        target, _, query = path.partition("?")
        binding_email = None
        if query.startswith("email="):
            binding_email = query[len("email="):].strip().lower()

        snapshot = self._load_snapshot(target.strip())
        if snapshot is None:
            return []

        records = self._snapshot_to_records(snapshot)
        if binding_email:
            for rec in records:
                if not any(fv.value == binding_email for fv in rec.emails):
                    rec.emails.insert(0, FieldValue(
                        value=binding_email,
                        source=self.name,
                        priority=self.priority,
                        raw=binding_email,
                        method="supplied",
                        warnings=[
                            "Email supplied externally via ?email= to link this GitHub "
                            "profile to a candidate identity -- the GitHub API did not "
                            "return it."
                        ],
                    ))
        return records

    # ------------------------------------------------------------------ #

    def _load_snapshot(self, target: str) -> dict | None:
        local = Path(target)
        if local.suffix.lower() == ".json" and local.exists():
            try:
                with open(local, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return self._fetch_live(_extract_username(target))

    def _fetch_live(self, username: str) -> dict | None:
        if not username:
            return None
        try:
            import requests
        except ImportError:
            return None
        try:
            profile_resp = requests.get(f"{_API_BASE}/users/{username}", timeout=_TIMEOUT_SECONDS)
            if profile_resp.status_code != 200:
                return None  # 404 / rate-limited / etc -- degrade gracefully
            profile = profile_resp.json()

            repos_resp = requests.get(
                f"{_API_BASE}/users/{username}/repos",
                params={"per_page": 100},
                timeout=_TIMEOUT_SECONDS,
            )
            repos = repos_resp.json() if repos_resp.status_code == 200 else []
            if not isinstance(repos, list):
                repos = []

            return {"profile": profile, "repos": repos}
        except Exception:
            return None  # network failure, malformed JSON, etc -- never crash

    def _snapshot_to_records(self, snapshot: dict) -> list[RawRecord]:
        profile = snapshot.get("profile") or {}
        repos = snapshot.get("repos") or []
        if not isinstance(profile, dict):
            return []

        def fv(value, raw=None, method="stated", **kw) -> FieldValue:
            return FieldValue(value=value, source=self.name, priority=self.priority, raw=raw or value, method=method, **kw)

        rec = RawRecord(source_name=self.name, source_priority=self.priority)

        name = (profile.get("name") or "").strip()
        if name:
            rec.full_name = fv(name)
        # No name is common on GitHub (public profiles often leave it blank).
        # We still return the record -- identity is established by the
        # username/binding-email, not by a name extracted here.

        loc_raw = (profile.get("location") or "").strip()
        if loc_raw:
            if "," in loc_raw:
                city_part, _, trailing = loc_raw.rpartition(",")
                city = city_part.strip() or None
                region, country_iso = resolve_region_or_country(trailing.strip())
            else:
                region, country_iso = resolve_region_or_country(loc_raw)
                city = loc_raw if region is None and country_iso is None else None
            rec.location = fv(Location(city=city, region=region, country=country_iso), raw=loc_raw, method="normalized")

        html_url = (profile.get("html_url") or "").strip()
        if html_url:
            rec.links["github"] = fv(html_url)

        blog = (profile.get("blog") or "").strip()
        if blog:
            portfolio_url = blog if blog.startswith("http") else f"https://{blog}"
            rec.links["portfolio"] = fv(portfolio_url, raw=blog)

        bio = (profile.get("bio") or "").strip()
        if bio:
            rec.headline = fv(bio)

        company = (profile.get("company") or "").strip()
        if company:
            exp = Experience(company=company.lstrip("@").strip(), title=None, start=None, end=None, summary=None)
            rec.experience.append(fv(exp, raw=company))

        seen: set[str] = set()
        for repo in repos:
            if not isinstance(repo, dict) or repo.get("fork"):
                continue  # forked repos aren't original work -- not evidence of authorship
            lang = (repo.get("language") or "").strip()
            key = lang.lower()
            if lang and key not in seen:
                seen.add(key)
                rec.skills.append(FieldValue(
                    value=lang,
                    source=self.name,
                    priority=self.priority,
                    raw=repo.get("name"),
                    method="inferred",
                    warnings=[
                        f"Skill '{lang}' inferred from GitHub repo language usage "
                        f"(repo: {repo.get('name')!r}) -- evidence of usage, not a stated claim."
                    ],
                ))

        return [rec]
