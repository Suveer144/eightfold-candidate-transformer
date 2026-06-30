import json
import pytest
from transformer.sources.github import GitHubSource, _extract_username

_FULL_SNAPSHOT = {
    "profile": {
        "login": "alicedev",
        "name": "Alice Johnson",
        "company": "@TechCorp",
        "location": "San Francisco, CA",
        "email": None,
        "bio": "Backend engineer",
        "html_url": "https://github.com/alicedev",
        "blog": "alicedev.dev",
    },
    "repos": [
        {"name": "api-service", "language": "Python", "fork": False},
        {"name": "old-fork", "language": "Java", "fork": True},
        {"name": "frontend", "language": "TypeScript", "fork": False},
        {"name": "api-service-2", "language": "Python", "fork": False},  # dup language
    ],
}

# Mirrors the real Suveer144 profile shape: name/company/location/bio all null
_SPARSE_SNAPSHOT = {
    "profile": {
        "login": "suveer144",
        "name": None,
        "company": None,
        "location": None,
        "email": None,
        "bio": None,
        "html_url": "https://github.com/suveer144",
        "blog": "",
    },
    "repos": [
        {"name": "Banking-app", "language": "Java", "fork": False},
        {"name": "MyTravelList", "language": "JavaScript", "fork": False},
    ],
}


def _write(tmp_path, data, name="snap.json"):
    f = tmp_path / name
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


# --- username/URL extraction -----------------------------------------------

def test_extract_username_from_url():
    assert _extract_username("https://github.com/Suveer144") == "Suveer144"


def test_extract_username_from_url_trailing_slash():
    assert _extract_username("https://github.com/Suveer144/") == "Suveer144"


def test_extract_username_bare():
    assert _extract_username("Suveer144") == "Suveer144"


def test_extract_username_at_prefix():
    assert _extract_username("@Suveer144") == "Suveer144"


# --- snapshot parsing --------------------------------------------------------

def test_full_snapshot_parses_name(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    records = GitHubSource().parse(str(f))
    assert len(records) == 1
    assert records[0].full_name.value == "Alice Johnson"


def test_company_becomes_experience_entry(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert len(r.experience) == 1
    exp = r.experience[0].value
    assert exp.company == "TechCorp"  # leading "@" stripped
    assert exp.title is None  # GitHub doesn't expose a title -- never guessed


def test_bio_becomes_headline(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.headline.value == "Backend engineer"


def test_html_url_becomes_github_link(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.links["github"].value == "https://github.com/alicedev"


def test_blog_becomes_portfolio_link(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.links["portfolio"].value == "https://alicedev.dev"


def test_location_city_country_split(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.location.value.city == "San Francisco"
    assert r.location.value.country == "US"


def test_skills_from_languages_excludes_forks(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    skill_values = {fv.value for fv in r.skills}
    assert "Python" in skill_values
    assert "TypeScript" in skill_values
    assert "Java" not in skill_values  # was only in the forked repo


def test_skills_deduplicated(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    skill_values = [fv.value for fv in r.skills]
    assert skill_values.count("Python") == 1  # appeared in 2 repos


def test_skill_method_is_inferred(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    python_skill = next(fv for fv in r.skills if fv.value == "Python")
    assert python_skill.method == "inferred"
    assert "evidence of usage" in python_skill.warnings[0]
    assert "not a stated claim" in python_skill.warnings[0]


def test_no_email_or_phone_from_github(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.emails == []
    assert r.phones == []


# --- sparse / real-world-like profile ---------------------------------------

def test_sparse_profile_no_name_still_returns_record(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    records = GitHubSource().parse(str(f))
    assert len(records) == 1
    assert records[0].full_name is None


def test_sparse_profile_no_location(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.location is None


def test_sparse_profile_no_headline(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.headline is None


def test_sparse_profile_no_portfolio_link(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert "portfolio" not in r.links  # empty blog -- never invent a URL


def test_sparse_profile_skills_still_extracted(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    skill_values = {fv.value for fv in r.skills}
    assert "Java" in skill_values
    assert "JavaScript" in skill_values


# --- identity binding (?email=) ----------------------------------------------

def test_binding_email_added(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    records = GitHubSource().parse(f"{f}?email=suveer.agarwala@gmail.com")
    assert len(records) == 1
    assert any(fv.value == "suveer.agarwala@gmail.com" for fv in records[0].emails)


def test_binding_email_carries_warning(tmp_path):
    f = _write(tmp_path, _SPARSE_SNAPSHOT)
    r = GitHubSource().parse(f"{f}?email=test@example.com")[0]
    email_fv = next(fv for fv in r.emails if fv.value == "test@example.com")
    assert "supplied externally" in email_fv.warnings[0]
    assert email_fv.method == "supplied"


def test_no_duplicate_binding_email_if_already_present(tmp_path):
    snapshot = dict(_FULL_SNAPSHOT)
    f = _write(tmp_path, snapshot)
    # _FULL_SNAPSHOT's profile.email is None, so github never emits an email
    # naturally -- binding should add exactly one
    r = GitHubSource().parse(f"{f}?email=alice@example.com")[0]
    assert len(r.emails) == 1


# --- robustness ---------------------------------------------------------

def test_missing_file_returns_empty():
    records = GitHubSource().parse("does/not/exist.json")
    assert records == []


def test_malformed_json_returns_empty(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json", encoding="utf-8")
    records = GitHubSource().parse(str(f))
    assert records == []


def test_empty_repos_list(tmp_path):
    snapshot = {"profile": {"name": "Bob"}, "repos": []}
    f = _write(tmp_path, snapshot)
    r = GitHubSource().parse(str(f))[0]
    assert r.skills == []


def test_non_list_repos_handled(tmp_path):
    snapshot = {"profile": {"name": "Bob"}, "repos": "not-a-list"}
    f = _write(tmp_path, snapshot)
    r = GitHubSource().parse(str(f))[0]
    assert r.skills == []


def test_non_dict_profile_returns_empty(tmp_path):
    snapshot = {"profile": "not-a-dict", "repos": []}
    f = _write(tmp_path, snapshot)
    records = GitHubSource().parse(str(f))
    assert records == []


def test_repo_entries_that_are_not_dicts_skipped(tmp_path):
    snapshot = {"profile": {"name": "Bob"}, "repos": [None, "garbage", {"name": "x", "language": "Go", "fork": False}]}
    f = _write(tmp_path, snapshot)
    r = GitHubSource().parse(str(f))[0]
    assert [fv.value for fv in r.skills] == ["Go"]


# --- live fetch (network mocked) ---------------------------------------

class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_live_fetch_success(monkeypatch):
    calls = []

    def fake_get(url, timeout=None, params=None):
        calls.append(url)
        if url.endswith("/users/octocat"):
            return _FakeResponse(200, {"login": "octocat", "name": "The Octocat"})
        if url.endswith("/users/octocat/repos"):
            return _FakeResponse(200, [{"name": "r1", "language": "Ruby", "fork": False}])
        raise AssertionError(f"unexpected url {url}")

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    records = GitHubSource().parse("octocat")
    assert len(records) == 1
    assert records[0].full_name.value == "The Octocat"
    assert [fv.value for fv in records[0].skills] == ["Ruby"]


def test_live_fetch_404_returns_empty(monkeypatch):
    def fake_get(url, timeout=None, params=None):
        return _FakeResponse(404, {"message": "Not Found"})

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    records = GitHubSource().parse("nonexistent-user-xyz")
    assert records == []


def test_live_fetch_network_error_returns_empty(monkeypatch):
    def fake_get(url, timeout=None, params=None):
        raise ConnectionError("simulated network failure")

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    records = GitHubSource().parse("anyuser")
    assert records == []  # never crashes


def test_live_fetch_repos_failure_still_returns_profile(monkeypatch):
    def fake_get(url, timeout=None, params=None):
        if "/repos" in url:
            return _FakeResponse(403, {"message": "rate limited"})
        return _FakeResponse(200, {"login": "x", "name": "X Person"})

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    records = GitHubSource().parse("x")
    assert len(records) == 1
    assert records[0].full_name.value == "X Person"
    assert records[0].skills == []


def test_empty_username_returns_empty():
    assert GitHubSource().parse("") == []


# --- priority -------------------------------------------------------------

def test_source_name_and_priority(tmp_path):
    f = _write(tmp_path, _FULL_SNAPSHOT)
    r = GitHubSource().parse(str(f))[0]
    assert r.source_name == "github"
    assert r.source_priority == 2  # between notes(1) and crm(3)
