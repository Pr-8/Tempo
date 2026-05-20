from redis import Redis
from rq import Queue
from datetime import datetime
import os
import logging

from scheduling.context_builder import build_scheduling_request
from solver.scheduler import solve_schedule
from llm.explainer import generate_schedule_explanation
from db import get_db_context
from models import ScheduledSession, UserPreferences

logger = logging.getLogger(__name__)

def run_reschedule_pipeline(user_id: str):
    """
    Orchestrates the full scheduling flow:
    Context Builder -> Solver -> DB Update -> LLM Explainer
    """
    with get_db_context() as db:
        # 1. Build scheduling request from DB state
        try:
            scheduling_request = build_scheduling_request(user_id, db)
        except ValueError as e:
            logger.error(f"Error building scheduling request: {e}")
            return None

        if not scheduling_request["tasks"]:
            return {"status": "NO_TASKS", "scheduled_sessions": [], "unschedulable_tasks": []}

        # 2. Run solver
        solver_output = solve_schedule(scheduling_request)
        
        # 3. Update DB: Delete all pending sessions for these tasks
        task_ids = [t["id"] for t in scheduling_request["tasks"]]
        db.query(ScheduledSession).filter(
            ScheduledSession.task_id.in_(task_ids),
            ScheduledSession.status == "pending"
        ).delete(synchronize_session=False)

        # 4. Insert new sessions if solve was successful
        if solver_output["status"] in ("OPTIMAL", "FEASIBLE"):
            for s in solver_output["scheduled_sessions"]:
                session = ScheduledSession(
                    task_id=s["task_id"],
                    start_time=datetime.fromisoformat(s["start"]),
                    end_time=datetime.fromisoformat(s["end"]),
                    status="pending"
                )
                db.add(session)

        # 5. Generate LLM explanation
        explanation = generate_schedule_explanation(solver_output, scheduling_request["tasks"])

        # 6. Update UserPreferences
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
        if prefs:
            prefs.last_schedule_explanation = explanation
            prefs.schedule_dirty = False
            
        db.commit()
        return solver_output

def mark_schedule_dirty(user_id: str):
    """
    Triggers a reschedule. Prefers async via RQ, falls back to sync if Redis is down.
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        redis_url = "redis://localhost:6379"
        
    try:
        redis_conn = Redis.from_url(redis_url, socket_connect_timeout=1)
        # Check connection
        redis_conn.ping()
        q = Queue("tempo_jobs", connection=redis_conn)
        q.enqueue(run_reschedule_pipeline, user_id)
        logger.info(f"Enqueued reschedule for user {user_id}")
    except Exception as e:
        logger.warning(f"Redis unavailable, running reschedule synchronously: {e}")
        return run_reschedule_pipeline(user_id)
