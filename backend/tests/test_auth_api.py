def test_login_success(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "nobody", "password": "test123"})
    assert resp.status_code == 401


def test_me_with_token(test_client, auth_headers):
    resp = test_client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_without_token(test_client):
    resp = test_client.get("/api/auth/me")
    assert resp.status_code == 403
