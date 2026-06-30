from transformer.normalizers.location import normalize_location


def test_us_code():
    assert normalize_location("US") == "US"


def test_usa_alias():
    assert normalize_location("USA") == "US"


def test_united_states():
    assert normalize_location("United States") == "US"


def test_uk_alias():
    assert normalize_location("UK") == "GB"


def test_united_kingdom():
    assert normalize_location("United Kingdom") == "GB"


def test_canada():
    assert normalize_location("Canada") == "CA"


def test_india():
    assert normalize_location("India") == "IN"


def test_unknown_returns_none():
    assert normalize_location("NotACountry") is None


def test_empty_returns_none():
    assert normalize_location("") is None


def test_case_insensitive():
    assert normalize_location("united states") == "US"
    assert normalize_location("INDIA") == "IN"
