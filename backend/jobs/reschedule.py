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
    print(f"DEBUG: Starting reschedule for {user_id}")
    with get_db_context() as db:
        # 1. Build scheduling request from DB state
        try:
            scheduling_request = build_scheduling_request(user_id, db)
            print(f"DEBUG: Request built with {len(scheduling_request['tasks'])} tasks")
        except ValueError as e:
            print(f"DEBUG: Context builder error: {e}")
            logger.error(f"Error building scheduling request: {e}")
            return None

        if not scheduling_request["tasks"]:
            print("DEBUG: No pending tasks found")
            return {"status": "NO_TASKS", "scheduled_sessions": [], "unschedulable_tasks": []}

        # 2. Run solver
        solver_output = solve_schedule(scheduling_request)
        print(f"DEBUG: Solver returned status {solver_output['status']} with {len(solver_output['scheduled_sessions'])} sessions")
        
        # 3. Update DB: Delete all pending sessions for these tasks
        task_ids = [t["id"] for t in scheduling_request["tasks"]]
        db.query(ScheduledSession).filter(
            ScheduledSession.task_id.in_(task_ids),
            ScheduledSession.status == "pending"
        ).delete(synchronize_session=False)
        print(f"DEBUG: Deleted old pending sessions")

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
            print(f"DEBUG: Inserted {len(solver_output['scheduled_sessions'])} new sessions")

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
    Triggers a reschedule. Synchronous for MVP stability.
    """
    return run_reschedule_pipeline(user_id)
