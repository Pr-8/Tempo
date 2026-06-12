from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime, timedelta, timezone

client = TestClient(app)

def test_create_task():
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    response = client.post(
        "/api/tasks/",
        json={
            "title": "Test Task",
            "course": "Test Course",
            "estimated_hours": 2.5,
            "deadline": deadline,
            "priority": 4
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["remaining_hours"] == 2.5
    assert data["status"] == "pending"

def test_read_tasks():
    response = client.get("/api/tasks/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_task():
    # Create first
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    create_res = client.post(
        "/api/tasks/",
        json={
            "title": "Update Me",
            "course": "Test",
            "estimated_hours": 1.0,
            "deadline": deadline
        },
    )
    task_id = create_res.json()["id"]
    
    # Update
    update_res = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Updated Title", "priority": 5}
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Title"
    assert update_res.json()["priority"] == 5

def test_delete_task():
    # Create first
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    create_res = client.post(
        "/api/tasks/",
        json={
            "title": "Delete Me",
            "course": "Test",
            "estimated_hours": 1.0,
            "deadline": deadline
        },
    )
    task_id = create_res.json()["id"]
    
    # Delete
    delete_res = client.delete(f"/api/tasks/{task_id}")
    assert delete_res.status_code == 200
    
    # Verify 404
    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 404
