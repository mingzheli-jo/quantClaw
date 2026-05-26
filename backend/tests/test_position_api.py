def test_create_position(test_client, auth_headers):
    resp = test_client.post(
        "/api/position/create",
        headers=auth_headers,
        json={"code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "600000"
    assert resp.json()["status"] == "open"


def test_list_positions(test_client, auth_headers):
    test_client.post(
        "/api/position/create",
        headers=auth_headers,
        json={"code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000},
    )
    resp = test_client.get("/api/position/list", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_close_position(test_client, auth_headers):
    create_resp = test_client.post(
        "/api/position/create",
        headers=auth_headers,
        json={"code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000},
    )
    pid = create_resp.json()["id"]
    resp = test_client.post(
        f"/api/position/{pid}/close",
        headers=auth_headers,
        json={"close_price": 11.0, "close_reason": "take_profit"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_stats_empty(test_client, auth_headers):
    resp = test_client.get("/api/position/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_trades"] == 0
