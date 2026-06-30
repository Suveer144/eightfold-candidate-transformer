"""Generates the one-page design document PDF for the Eightfold assignment submission."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable

OUT_PATH = r"C:\Users\suvee\Desktop\assignment\Suveer Agarwala_suveer.agarwala@gmail.com_Eightfold.pdf"

NAVY = colors.HexColor("#1F3864")
GREY = colors.HexColor("#444444")

doc = SimpleDocTemplate(
    OUT_PATH,
    pagesize=letter,
    topMargin=0.4 * inch,
    bottomMargin=0.35 * inch,
    leftMargin=0.5 * inch,
    rightMargin=0.5 * inch,
)

title_style = ParagraphStyle(
    "Title", fontName="Helvetica-Bold", fontSize=13.5, textColor=NAVY,
    spaceAfter=2, leading=16,
)
subtitle_style = ParagraphStyle(
    "Subtitle", fontName="Helvetica", fontSize=8.5, textColor=GREY,
    spaceAfter=6, leading=10,
)
h2 = ParagraphStyle(
    "H2", fontName="Helvetica-Bold", fontSize=9.3, textColor=NAVY,
    spaceBefore=5, spaceAfter=2, leading=11,
)
body = ParagraphStyle(
    "Body", fontName="Helvetica", fontSize=7.9, textColor=colors.black,
    leading=10.1, alignment=TA_LEFT, spaceAfter=1.5,
)
bullet = ParagraphStyle(
    "Bullet", parent=body, leftIndent=10, bulletIndent=2, spaceAfter=1.5,
)
mono = ParagraphStyle(
    "Mono", fontName="Courier", fontSize=7.3, textColor=colors.black,
    leading=9.5, spaceAfter=1.5, backColor=colors.HexColor("#F2F2F2"),
)

story = []

story.append(Paragraph("Multi-Source Candidate Data Transformer", title_style))
story.append(Paragraph(
    "Design Document &nbsp;|&nbsp; Suveer Agarwala &nbsp;|&nbsp; Eightfold Engineering Intern Assignment",
    subtitle_style,
))
story.append(HRFlowable(width="100%", thickness=0.8, color=NAVY, spaceAfter=3))

story.append(Paragraph(
    "<b>Pipeline:</b> ingest (CSV / regex / REST API) &rarr; extract per-field with method tag "
    "(stated/extracted/inferred/normalized/supplied) &rarr; normalize (phone E.164, location ISO, skill "
    "casing) &rarr; merge across sources (priority + union, conflicts logged) &rarr; score confidence "
    "(per-skill and overall) &rarr; project via runtime config (rename/select/normalize) &rarr; validate "
    "against the requested schema &rarr; emit JSON (valid candidates separate from invalid ones).",
    body,
))

# 1. Sources
story.append(Paragraph("1. Sources", h2))
story.append(Paragraph(
    "<b>Structured &mdash; Recruiter CSV export, priority 3 (highest):</b> recruiter-curated/verified system of "
    "record. Columns: name, email, phone, current_company, title, location, skills, years_experience, "
    "education. (The assignment lists CSV and a separate &ldquo;ATS JSON blob&rdquo; as alternative "
    "structured-source picks with different field-naming conventions &mdash; we picked CSV only; JSON is "
    "intentionally out of scope.)",
    bullet,
))
story.append(Paragraph(
    "<b>Unstructured &mdash; Recruiter notes (free text), priority 1 (lowest):</b> informal, ad-hoc; "
    "regex-heuristic extraction of name, contact, current role/company, location, skills, education.",
    bullet,
))
story.append(Paragraph(
    "<b>Unstructured &mdash; GitHub profile (public REST API), priority 2:</b> self-maintained but unverified "
    "and often sparse &mdash; a real test profile returned null for name, company, location, bio, and email. "
    "Maps: html_url&rarr;links.github, blog&rarr;links.portfolio, bio&rarr;headline, company&rarr;experience, "
    "repo languages (forks excluded)&rarr;skills (evidence of usage, not a stated claim &mdash; lower "
    "per-skill confidence, flagged in provenance). <b>Network dependency:</b> live fetches need GitHub's API "
    "reachable and within its 60 req/hr unauthenticated rate limit; failures degrade to an empty result, "
    "never a crash. A cached JSON snapshot supports deterministic offline runs.",
    bullet,
))

# 2. Canonical schema
story.append(Paragraph("2. Canonical Schema", h2))
story.append(Paragraph(
    "candidate_id (string) &middot; full_name (string|null) &middot; emails (string[]) &middot; "
    "phones (string[], E.164) &middot; location ({city, region, country: ISO 3166-1 alpha-2}) &middot; "
    "links ({linkedin, github, portfolio, other[]}) &middot; headline (string|null) &middot; "
    "years_experience (number|null) &middot; skills ([{name, confidence, sources[]}]) &middot; "
    "experience ([{company, title, start, end, summary}], dates as YYYY-MM) &middot; "
    "education ([{institution, degree, field, end_year}]) &middot; "
    "provenance ([{field, source, method}]) &middot; overall_confidence (number, 0&ndash;1). "
    "Provenance and overall_confidence are part of the default output, not opt-in extras.",
    body,
))

# 3. Normalization
story.append(Paragraph("3. Normalization", h2))
story.append(Paragraph(
    "<b>Phone &rarr; E.164</b> via <i>phonenumbers</i>, including non-US country codes (e.g. +91); numbers "
    "that fail to parse are kept as the raw string and flagged, never dropped.", bullet,
))
story.append(Paragraph(
    "<b>Country &rarr; ISO 3166-1 alpha-2</b> via <i>pycountry</i> plus an alias table. A bare 2-letter code "
    "is ambiguous (&ldquo;CA&rdquo; = California or Canada's ISO code?) and is only resolved to a country "
    "when it matches a genuine US state abbreviation; otherwise kept as the stated region with country left "
    "null rather than guessed.", bullet,
))
story.append(Paragraph("<b>Dates &rarr; ISO 8601 / YYYY-MM</b> via <i>dateutil</i> where applicable.", bullet))
story.append(Paragraph(
    "<b>Skills &rarr; canonical names</b> by default (not just opt-in): casing/alias normalization "
    "(javascript&rarr;JavaScript, sql&rarr;SQL, nodejs/node.js&rarr;Node.js) applied during merge so the "
    "same skill from different sources converges into one entry, satisfying the schema's &ldquo;canonical "
    "skill names&rdquo; note.", bullet,
))

# 4. Merge policy
story.append(Paragraph("4. Merge &amp; Conflict-Resolution Policy", h2))
story.append(Paragraph(
    "<b>Identity:</b> grouped by shared email (primary) or exact normalized full_name (fallback). GitHub "
    "profiles often expose neither &mdash; the caller supplies an explicit "
    "<font face='Courier'>?email=</font> binding on the source path, a stated fact, never a fuzzy match.",
    bullet,
))
story.append(Paragraph(
    "<b>Scalar fields</b> (full_name, location, headline, years_experience): highest-priority source wins "
    "(CRM &gt; GitHub &gt; notes); conflicts logged with both values and sources.", bullet,
))
story.append(Paragraph(
    "<b>List fields</b> (emails, phones, education): unioned, deduplicated by normalized value.", bullet,
))
story.append(Paragraph(
    "<b>Skills:</b> grouped by normalized name across sources; confidence = "
    "max(method-base-confidence) + 0.1 &times; (extra corroborating sources), capped at 1.0. Method-base: "
    "stated=.9, normalized=.85, extracted=.75, supplied=.6, inferred=.5.", bullet,
))
story.append(Paragraph(
    "<b>Experience:</b> grouped by company only (not company+title) &mdash; a company match is a strong "
    "same-job signal even when sources phrase the title differently; title then resolves like any other "
    "scalar, with a conflict logged if sources disagree.", bullet,
))

# 5. Runtime config
story.append(Paragraph("5. Runtime Config (reshapes output, no code changes)", h2))
story.append(Paragraph(
    "A JSON config supplies a <font face='Courier'>fields</font> array of "
    "{path, from, type, required, normalize}. <font face='Courier'>path</font> is the output key; "
    "<font face='Courier'>from</font> is a path into the canonical record supporting dotted access "
    "(location.city), indexing (emails[0]), and flatten-map (skills[].name). "
    "<font face='Courier'>normalize</font>: E164 or canonical. "
    "<font face='Courier'>on_missing</font>: null | omit | error (error only fires for required fields and "
    "routes the whole candidate to a separate invalid_candidates list with reasons, rather than discarding "
    "it). <font face='Courier'>include_confidence</font> / <font face='Courier'>include_provenance</font> "
    "toggle those sections. No config &rarr; full canonical schema, untouched. Every output (default or "
    "reshaped) is validated against the relevant schema (the default field types, or the config's own "
    "declared types) before being returned &mdash; type mismatches route the candidate to "
    "invalid_candidates instead of returning bad data silently.", body,
))

# 6. Edge cases
story.append(Paragraph("6. Edge Cases", h2))
story.append(Paragraph(
    "<b>1.</b> GitHub profile with no name/email &rarr; never fuzzy-matched; requires an explicit identity "
    "binding or remains a standalone candidate.", bullet,
))
story.append(Paragraph(
    "<b>2.</b> Year ranges in notes (&ldquo;3&ndash;5 years&rdquo;) &rarr; stated lower bound only, never "
    "the midpoint.", bullet,
))
story.append(Paragraph(
    "<b>3.</b> Ambiguous location codes &rarr; resolved to a country only for confirmed US state codes "
    "(caught on a real profile: &ldquo;KA&rdquo; for Karnataka, India was initially mis-resolved to the US).",
    bullet,
))
story.append(Paragraph(
    "<b>4.</b> Same job, different title per source (e.g. &ldquo;Data Scientist&rdquo; vs &ldquo;Senior Data "
    "Scientist&rdquo;) &rarr; merged into one experience entry by company, not duplicated; title conflict "
    "logged.", bullet,
))
story.append(Paragraph(
    "<b>5.</b> Missing required config field under on_missing=error &rarr; candidate routed to "
    "invalid_candidates with a reason, run continues; never silently dropped or fabricated.", bullet,
))

# 7. Confidence
story.append(Paragraph("7. Confidence Formula", h2))
story.append(Paragraph(
    "overall_confidence = clamp( &Sigma; weight[f] for each filled required field &minus; "
    "0.05&times;normalization_failures &minus; 0.05&times;conflicts, &nbsp;0, &nbsp;1 )", mono,
))
story.append(Paragraph(
    "Weights: full_name .25, emails .20, skills .15, phones/location/years_experience/experience .10 each. "
    "Records below the 0.4 threshold are flagged, not dropped, by default.", body,
))

doc.build(story)
print("PDF written to", OUT_PATH)
