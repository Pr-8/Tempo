from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_preferences():
    response = client.get("/api/preferences/")
    assert response.status_code == 200
    data = response.json()
    assert "available_start_hour" in data
    assert "available_days" in data

def test_update_preferences():
    new_prefs = {
        "available_start_hour": 8,
        "available_end_hour": 20,
        "available_days": [0, 1, 2, 3, 4, 5],
        "min_session_minutes": 45,
        "max_session_minutes": 180,
        "max_sessions_per_day": 5,
        "min_break_minutes": 30,
        "planning_horizon_days": 14
    }
    response = client.put("/api/preferences/", json=new_prefs)
    assert response.status_code == 200
    data = response.json()
    assert data["available_start_hour"] == 8
    assert data["planning_horizon_days"] == 14
