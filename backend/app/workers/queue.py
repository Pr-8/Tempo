from redis import Redis
from rq import Queue
from app.core.config import settings

redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue("tempo_tasks", connection=redis_conn)

def enqueue_regeneration():
    """Enqueues the regeneration job, avoiding duplicates if one is already queued."""
    # Simple debouncing: check if job is already in queue
    job_id = "regenerate_schedule_singleton"
    existing_job = queue.fetch_job(job_id)
    
    if existing_job and existing_job.get_status() in ['queued', 'started']:
        return # Already working on it
        
    queue.enqueue(
        "app.workers.jobs.regenerate_schedule_job",
        job_id=job_id,
        result_ttl=500
    )
