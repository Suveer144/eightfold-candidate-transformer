# Candidate Data Transformer

Multi-source candidate profile normaliser — Eightfold Engineering Intern assignment.

Ingests a structured CRM export (CSV) and two unstructured sources (recruiter notes, GitHub profile), merges them by identity, normalises fields, scores confidence, and reshapes the output through a runtime JSON config — no code changes. Full design rationale is in `Suveer Agarwala_suveer.agarwala@gmail.com_Eightfold.pdf`.

## Setup

```bash
pip install -r requirements.txt
```

Python 3.10+. (`pip install -e .` is optional — `python -m transformer.cli` works the same without it.)

## How to run

**Sample data:**
```bash
candidate-transformer run \
  --source crm:data/samples/crm_export.csv \
  --source notes:data/samples/recruiter_notes.txt
```

**Real profile, live GitHub fetch** (all 3 sources merged into one candidate):
```bash
candidate-transformer run \
  --source crm:data/samples/crm_export_real.csv \
  --source notes:data/samples/recruiter_notes_real.txt \
  --source "github:Suveer144?email=suveer.agarwala@gmail.com"
```

The `?email=` is required — this GitHub profile's API response has `name`, `company`, `location`, and `email` all `null`, so without an explicit binding there's nothing to match it to the CRM/notes record.

**Reshape output via config** (rename fields, normalize, select a subset — see `config/reshape_example.json`):
```bash
candidate-transformer run \
  --source crm:data/samples/crm_export_real.csv \
  --source notes:data/samples/recruiter_notes_real.txt \
  --source "github:Suveer144?email=suveer.agarwala@gmail.com" \
  --config config/reshape_example.json
```

## Sample output

Full output on the real profile (3 sources merged: CRM + recruiter notes + live GitHub fetch). Also saved at `output/real_profile_default.json`.

**Default (full canonical schema):**

```json
{
  "candidate_id": "C05246377247A",
  "full_name": "Suveer Agarwala",
  "emails": ["suveer.agarwala@gmail.com"],
  "phones": ["+917414872335"],
  "location": { "city": "Manipal", "region": "Karnataka", "country": "IN" },
  "links": { "linkedin": null, "github": "https://github.com/Suveer144", "portfolio": null, "other": [] },
  "headline": null,
  "years_experience": null,
  "skills": [
    { "name": "Python", "confidence": 1.0, "sources": ["crm", "github", "notes"] },
    { "name": "Machine Learning", "confidence": 0.75, "sources": ["notes"] },
    { "name": "LangChain", "confidence": 0.75, "sources": ["notes"] },
    { "name": "RAG pipelines", "confidence": 0.75, "sources": ["notes"] },
    { "name": "C#", "confidence": 1.0, "sources": ["crm", "github"] },
    { "name": "Java", "confidence": 1.0, "sources": ["crm", "github"] },
    { "name": "HTML", "confidence": 0.5, "sources": ["github"] },
    { "name": "JavaScript", "confidence": 1.0, "sources": ["crm", "github"] },
    { "name": "SQL", "confidence": 0.9, "sources": ["crm"] },
    { "name": "C", "confidence": 0.9, "sources": ["crm"] }
  ],
  "experience": [
    { "company": "Curavolv", "title": "AI and Software Development Intern", "start": null, "end": null, "summary": null }
  ],
  "education": [
    { "institution": "Manipal Institute of Technology", "degree": "B.Tech", "field": "Information Technology", "end_year": 2027 }
  ],
  "provenance": [
    { "field": "full_name", "source": "crm", "method": "stated" },
    { "field": "location", "source": "crm", "method": "normalized" },
    { "field": "emails", "source": "notes", "method": "extracted" },
    { "field": "emails", "source": "github", "method": "supplied" },
    { "field": "emails", "source": "crm", "method": "stated" },
    { "field": "phones", "source": "notes", "method": "normalized" },
    { "field": "phones", "source": "crm", "method": "normalized" },
    { "field": "skills", "source": "notes", "method": "extracted" },
    { "field": "skills", "source": "github", "method": "inferred" },
    { "field": "skills", "source": "crm", "method": "stated" },
    { "field": "experience", "source": "notes", "method": "extracted" },
    { "field": "experience", "source": "crm", "method": "stated" },
    { "field": "education", "source": "notes", "method": "extracted" },
    { "field": "education", "source": "crm", "method": "stated" },
    { "field": "links.github", "source": "github", "method": "stated" }
  ],
  "overall_confidence": 0.85
}
```

A few fields are legitimately `null` as can be seen above and it is not a bug; this is the "never assume" rule working as intended.

**Reshaped, via `config/reshape_example.json`** (rename, E.164/canonical normalization, field subset — `provenance` is still included by default unless a config explicitly turns it off):

```json
{
  "full_name": "Suveer Agarwala",
  "primary_email": "suveer.agarwala@gmail.com",
  "phone": "+917414872335",
  "skills": ["python", "machine learning", "langchain", "rag pipelines", "c#", "java", "html", "javascript", "sql", "c"],
  "overall_confidence": 0.85,
  "provenance": [
    { "field": "full_name", "source": "crm", "method": "stated" },
    { "field": "location", "source": "crm", "method": "normalized" },
    { "field": "emails", "source": "notes", "method": "extracted" },
    { "field": "emails", "source": "github", "method": "supplied" },
    { "field": "emails", "source": "crm", "method": "stated" },
    { "field": "phones", "source": "notes", "method": "normalized" },
    { "field": "phones", "source": "crm", "method": "normalized" },
    { "field": "skills", "source": "notes", "method": "extracted" },
    { "field": "skills", "source": "github", "method": "inferred" },
    { "field": "skills", "source": "crm", "method": "stated" },
    { "field": "experience", "source": "notes", "method": "extracted" },
    { "field": "experience", "source": "crm", "method": "stated" },
    { "field": "education", "source": "notes", "method": "extracted" },
    { "field": "education", "source": "crm", "method": "stated" },
    { "field": "links.github", "source": "github", "method": "stated" }
  ]
}
```

`output/` holds these exact captures (`real_profile_default.json`, `real_profile_reshaped.json`) plus a fictional-data run, so you can diff against a fresh run yourself.

## Source types

| Type | Format | Notes |
|---|---|---|
| `crm` | `.csv` | structured — see `crm_export.csv` for columns |
| `notes` | `.txt` | free-text recruiter notes, blocks split by `---` |
| `github` | username, profile URL, or local `.json` snapshot | public REST API; `?email=` binds identity |

## Assumptions & descoped

- **Dates** (`experience[].start/end` as YYYY-MM) are never populated — none of our 3 sources state clean start/end dates, and we don't guess them. The normalizer exists and is tested; it's just never exercised by current data.
- **Past roles** are not extracted from recruiter notes — only the current role (notes prose rarely states clean dates for prior roles, and guessing would violate the never-assume rule). CRM and GitHub are inherently single-role-per-record anyway.
- **`links.linkedin`** is never populated — we don't have a LinkedIn source. It will stay `null` until one exists; we don't fabricate a URL.
- **Education institution** is only captured when explicitly stated near the degree/field in the source text (CRM has a dedicated column; notes relies on regex around "from"/"at"/comma-separated school names).
- **Skill canonicalization** is best-effort casing/alias normalization (e.g. `javascript`→`JavaScript`, `sql`→`SQL`), not a full taxonomy. Uncommon multi-word skill phrases can keep imperfect casing but also keep deduplicating correctly.

## Tests

```bash
pytest
```

156 tests covering all 3 sources, every normalizer, the merger (incl. multi-source priority resolution and gap-filling across duplicate entries), confidence scoring, schema validation, the config path-resolution engine, and full pipeline integration.
