from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime, timedelta, timezone
import uuid

client = TestClient(app)

def test_session_actions():
    # 1. Create a task
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    task_res = client.post("/api/tasks/", json={
        "title": "Action Task",
        "course": "Test",
        "estimated_hours": 2.0,
        "deadline": deadline
    })
    task_id = task_res.json()["id"]
    
    # 2. Manually create a session (since background worker might not have run)
    # Note: In real usage, the solver creates these.
    from app.core.database import SessionLocal
    from app.models.session import Session as SessionModel
    db = SessionLocal()
    sess_id = uuid.uuid4()
    db_sess = SessionModel(
        id=sess_id,
        task_id=task_id,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        duration_minutes=60,
        status="scheduled",
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_sess)
    db.commit()
    db.close()

    # 3. Complete session
    comp_res = client.patch(f"/api/sessions/{sess_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["remaining_hours"] == 1.0 # 2.0 - 1.0
    
    # 4. Create another session and fail it
    db = SessionLocal()
    sess_id_2 = uuid.uuid4()
    db_sess_2 = SessionModel(
        id=sess_id_2,
        task_id=task_id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        duration_minutes=60,
        status="scheduled",
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_sess_2)
    db.commit()
    db.close()

    fail_res = client.patch(f"/api/sessions/{sess_id_2}/failed")
    assert fail_res.status_code == 200
    assert fail_res.json()["remaining_hours"] == 1.0 # Unchanged
