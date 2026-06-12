from fastapi.testclient import TestClient
from app.main import app
from app.workers.queue import redis_conn, queue

client = TestClient(app)

def test_trigger_regeneration():
    # Clear queue
    queue.empty()
    
    # Trigger via manual endpoint
    response = client.post("/api/schedule/regenerate")
    assert response.status_code == 200
    
    # Check if job is in queue
    job = queue.fetch_job("regenerate_schedule_singleton")
    assert job is not None
