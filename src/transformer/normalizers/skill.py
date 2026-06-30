from __future__ import annotations

# Multi-word/internally-capitalized terms that a naive title-case would mangle
# (e.g. "javascript".capitalize() -> "Javascript", not "JavaScript").
_CANONICAL_FORMS: dict[str, str] = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "github": "GitHub",
    "gitlab": "GitLab",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "langchain": "LangChain",
    "graphql": "GraphQL",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "devops": "DevOps",
    "c#": "C#",
    "c++": "C++",
    ".net": ".NET",
}

# Short acronyms/initialisms that should stay fully uppercase
_KNOWN_ACRONYMS: frozenset[str] = frozenset({
    "sql", "html", "css", "api", "rest", "ai", "ml", "llm", "llms", "rag",
    "aws", "gcp", "json", "xml", "ui", "ux", "saas", "nlp", "cv", "gpu",
    "cpu", "db", "orm", "jwt", "oauth", "http", "https", "tcp", "udp", "ip",
    "dns", "cdn", "ide", "cli", "sdk", "vm", "k8s", "ci", "cd", "qa", "etl",
})


def canonicalize_skill(name: str) -> str:
    """
    Produce a consistent display form for a skill name so the same skill from
    different sources ("python" vs "Python" vs "PYTHON") converges on one
    canonical spelling -- satisfies the schema's "canonical skill names" note.
    Never raises; unrecognized input is returned with best-effort title casing,
    or as-is if it already has meaningful internal capitalization we don't
    have a rule for (e.g. an unfamiliar CamelCase library name).
    """
    cleaned = " ".join((name or "").strip().split())
    if not cleaned:
        return cleaned

    key = cleaned.lower()
    if key in _CANONICAL_FORMS:
        return _CANONICAL_FORMS[key]

    if not cleaned.islower() and not cleaned.isupper():
        return cleaned  # already has non-trivial mixed case -- trust the source

    words = cleaned.split(" ")
    out_words = []
    for w in words:
        wl = w.lower().strip(".,")
        out_words.append(w.upper() if wl in _KNOWN_ACRONYMS else w.capitalize())
    return " ".join(out_words)
