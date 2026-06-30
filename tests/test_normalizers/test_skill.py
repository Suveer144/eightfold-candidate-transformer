from transformer.normalizers.skill import canonicalize_skill


def test_lowercase_single_word():
    assert canonicalize_skill("python") == "Python"


def test_uppercase_single_word():
    assert canonicalize_skill("PYTHON") == "Python"


def test_known_acronym_stays_uppercase():
    assert canonicalize_skill("sql") == "SQL"
    assert canonicalize_skill("SQL") == "SQL"
    assert canonicalize_skill("html") == "HTML"


def test_known_camel_case_term():
    assert canonicalize_skill("javascript") == "JavaScript"
    assert canonicalize_skill("JAVASCRIPT") == "JavaScript"
    assert canonicalize_skill("JavaScript") == "JavaScript"


def test_special_case_csharp():
    assert canonicalize_skill("c#") == "C#"
    assert canonicalize_skill("C#") == "C#"


def test_acronym_plus_word():
    assert canonicalize_skill("rag pipelines") == "RAG Pipelines"


def test_already_mixed_case_unknown_term_preserved():
    assert canonicalize_skill("LangChain") == "LangChain"
    assert canonicalize_skill("langchain") == "LangChain"  # via dict


def test_whitespace_collapsed():
    assert canonicalize_skill("  machine   learning  ") == "Machine Learning"


def test_empty_string():
    assert canonicalize_skill("") == ""


def test_node_js_alias_normalized():
    assert canonicalize_skill("nodejs") == "Node.js"
    assert canonicalize_skill("node.js") == "Node.js"
