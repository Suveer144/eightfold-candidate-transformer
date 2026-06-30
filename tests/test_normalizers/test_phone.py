from transformer.normalizers.phone import normalize_phone


def test_us_parens_format():
    normalized, warn = normalize_phone("(415) 555-0101")
    assert normalized == "+14155550101"
    assert warn is None


def test_us_dashes():
    normalized, warn = normalize_phone("415-555-0101")
    assert normalized == "+14155550101"
    assert warn is None


def test_with_country_code():
    normalized, warn = normalize_phone("+1 212 555 0102")
    assert normalized == "+12125550102"
    assert warn is None


def test_dots_format():
    normalized, warn = normalize_phone("415.555.0101")
    assert normalized == "+14155550101"
    assert warn is None


def test_international():
    normalized, warn = normalize_phone("+44 20 7946 0958")
    assert normalized == "+442079460958"
    assert warn is None


def test_invalid_too_short():
    normalized, warn = normalize_phone("12345")
    assert normalized is None
    assert warn is not None


def test_garbage_string():
    normalized, warn = normalize_phone("not-a-phone")
    assert normalized is None
    assert warn is not None


def test_empty_string():
    normalized, warn = normalize_phone("")
    assert normalized is None
