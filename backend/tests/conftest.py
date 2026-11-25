import os
import sys
import tempfile
from pathlib import Path

DB_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(DB_DIR.name) / "test.db")
os.environ["JWT_SECRET"] = "test-only-long-random-secret-1234567890123456789"
os.environ["ADMIN_EMAIL"] = "chair@example.org"
os.environ["ADMIN_PASSWORD"] = "1234567890123456"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.main import app
from app.db import SessionLocal
from app.models import Audit, EntryPlayer, Match, Entry, Competition, Player, Team, Admin


@pytest.fixture
def client():
    with TestClient(app) as c:
        with SessionLocal.begin() as db:
            for model in [Audit, Match, EntryPlayer, Entry, Competition, Player, Team]:
                db.execute(delete(model))
        yield c


@pytest.fixture
def admin(client):
    assert client.post("/api/auth/login", json={"email": "chair@example.org", "password": "1234567890123456"}).status_code == 200
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.headers.update({"X-CSRF-Token": csrf})
    return client
