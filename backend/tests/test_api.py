"""Smoke + integration tests for the Wilayat API."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_list_surahs():
    r = client.get("/api/quran/surahs")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(s["en"] == "Al-Fatihah" for s in body["surahs"])


def test_get_fatiha_has_seven_verses():
    r = client.get("/api/quran/surah/1")
    assert r.status_code == 200
    assert len(r.json()["verses"]) == 7


def test_hadith_search():
    r = client.get("/api/hadith/search", params={"q": "knowledge"})
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_prayer_times():
    r = client.get("/api/prayer/times", params={"lat": 21.4, "lng": 39.8})
    assert r.status_code == 200
    assert len(r.json()["times"]) == 6


def test_ai_refuses_rulings():
    r = client.post("/api/ai/ask", json={"question": "Is it halal to do X?"})
    assert r.status_code == 200
    body = r.json()
    assert body["requires_scholar"] is True
    assert body["reference"]


def test_auth_register_and_me():
    r = client.post("/api/auth/register", json={
        "email": "ali@example.com", "name": "Ali", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ali@example.com"
