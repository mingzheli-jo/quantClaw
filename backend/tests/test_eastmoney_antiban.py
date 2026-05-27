from app.services.data.providers.eastmoney import _USER_AGENTS, _random_headers


def test_random_headers_returns_valid_headers():
    headers = _random_headers()
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert headers["User-Agent"] in _USER_AGENTS


def test_random_headers_varies():
    results = set()
    for _ in range(50):
        h = _random_headers()
        results.add(h["User-Agent"])
    assert len(results) > 1
