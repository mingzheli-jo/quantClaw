from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.system import User
from app.utils.security import hash_password

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def test_client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    db_session.add(User(username="admin", hashed_password=hash_password("test123")))
    db_session.commit()
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_kline_df():
    dates = pd.bdate_range(end=date.today(), periods=30)
    base = 20.0
    rows = []
    for i, d in enumerate(dates):
        c = base + i * 0.2
        rows.append({"code": "600000", "trade_date": d.date(), "open": c - 0.1, "high": c + 0.3, "low": c - 0.2, "close": c, "volume": 1000000 * (10 + i), "amount": c * 1000000 * (10 + i)})
    return pd.DataFrame(rows)
