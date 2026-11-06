from fastapi.testclient import TestClient
from sqlalchemy import text

from app import db
from app.main import app
from tests.conftest import make_client


def test_register_login_me_and_protection():
    c = TestClient(app)
    assert c.get("/api/notes").status_code == 401
    assert c.get("/api/notes", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = c.post("/api/auth/register", json={"email": "Me@Example.com", "password": "longenough1", "display_name": "Me"})
    assert r.status_code == 201 and r.json()["user"]["email"] == "me@example.com"
    assert "password" not in r.text
    r = c.post("/api/auth/login", json={"email": "me@example.com", "password": "longenough1"})
    tok = r.json()["access_token"]
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["display_name"] == "Me"


def test_validation_and_duplicates():
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"email": "bad", "password": "longenough1"}).status_code == 422
    assert c.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    assert c.post("/api/auth/register", json={"email": "a@b.co", "password": "longenough1"}).status_code == 201
    assert c.post("/api/auth/register", json={"email": "A@B.co", "password": "longenough1"}).status_code == 409


def test_wrong_password_and_lockout():
    c = make_client("x@example.com")
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "x@example.com", "password": "wrong-password"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "x@example.com", "password": "correct-horse"}).status_code == 429


def test_profile_prefs_and_password_change():
    c = make_client()
    r = c.patch("/api/auth/me", json={"display_name": "Khushi", "prefs": {"reduce_motion": True}})
    assert r.json()["display_name"] == "Khushi" and r.json()["prefs"] == {"reduce_motion": True}
    assert c.post("/api/auth/password", json={"current_password": "nope-nope", "new_password": "brand-new-pass"}).status_code == 400
    assert c.post("/api/auth/password", json={"current_password": "correct-horse", "new_password": "brand-new-pass"}).status_code == 204
    assert TestClient(app).post("/api/auth/login", json={"email": "a@example.com", "password": "brand-new-pass"}).status_code == 200


def test_legacy_notes_adopted_by_first_account_only():
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO notes (id, title, content, content_hash) VALUES (gen_random_uuid(), 'old', 'x', 'h')"))
    first, second = make_client("first@example.com"), make_client("second@example.com")
    assert [n["title"] for n in first.get("/api/notes").json()] == ["old"]
    assert second.get("/api/notes").json() == []
