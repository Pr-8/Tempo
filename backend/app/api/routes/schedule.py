from fastapi import APIRouter
from app.workers.queue import enqueue_regeneration, redis_conn
from rq import Queue

router = APIRouter(prefix="/schedule", tags=["schedule"])

@router.post("/regenerate")
def manual_regenerate():
    enqueue_regeneration()
    return {"status": "enqueued"}

@router.get("/status")
def get_status():
    q = Queue("tempo_tasks", connection=redis_conn)
    job = q.fetch_job("regenerate_schedule_singleton")
    
    status = "idle"
    if job:
        status = job.get_status()
    
    return {"status": status}
