from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import List
import asyncio

from app.models.task import Task as TaskModel
from app.models.session import Session as SessionModel
from app.models.preferences import UserPreferences as PreferencesModel
from app.models.schedule import ScheduleRun
from app.services.solver.scheduler import TempoScheduler
from app.services.solver.models import SolverTask, SolverPreferences
from app.services.llm.gemini import generate_schedule_explanation
from app.core.ws_manager import manager

def run_scheduling_pipeline(db: Session):
    print("DEBUG: Starting run_scheduling_pipeline")
    # 0. Track run
    now = datetime.now()
    run = ScheduleRun(
        started_at=now,
        status='running'
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 1. Collect Data
    tasks = db.query(TaskModel).filter(TaskModel.status.in_(['pending', 'in_progress'])).all()
    prefs_db = db.query(PreferencesModel).first()
    print(f"DEBUG: Found {len(tasks)} tasks and preferences: {prefs_db is not None}")
    
    if not prefs_db:
        run.completed_at = datetime.now()
        run.status = 'failed'
        run.infeasible_reason = "User preferences not found"
        db.commit()
        return 0

    solver_tasks = [
        SolverTask(
            id=t.id, 
            title=t.title, 
            course=t.course,
            remaining_hours=t.remaining_hours, 
            deadline=t.deadline, 
            priority=t.priority,
            is_fixed=t.is_fixed,
            fixed_start=t.fixed_start,
            fixed_end=t.fixed_end
        ) for t in tasks
    ]
    
    solver_prefs = SolverPreferences(
        available_start_hour=prefs_db.available_start_hour,
        available_end_hour=prefs_db.available_end_hour,
        available_days=prefs_db.available_days,
        min_session_minutes=prefs_db.min_session_minutes,
        max_session_minutes=prefs_db.max_session_minutes,
        max_sessions_per_day=prefs_db.max_sessions_per_day,
        min_break_minutes=prefs_db.min_break_minutes,
        planning_horizon_days=prefs_db.planning_horizon_days,
        blocked_dates=[d.strip() for d in prefs_db.blocked_dates.split(",") if d.strip()]
    )

    # 2. Delete FUTURE scheduled sessions
    db.query(SessionModel).filter(
        SessionModel.status == 'scheduled',
        SessionModel.start_time > now
    ).delete()
    print("DEBUG: Deleted future sessions")
    
    # 3. Run Solver
    print("DEBUG: Starting solver...")
    scheduler = TempoScheduler(solver_tasks, solver_prefs, now)
    scheduled_sessions = scheduler.solve()
    print(f"DEBUG: Solver finished. Found {len(scheduled_sessions)} sessions.")
    
    # 4. Save results
    for s in scheduled_sessions:
        db_session = SessionModel(
            task_id=s.task_id,
            start_time=s.start_time,
            end_time=s.end_time,
            duration_minutes=s.duration_minutes,
            status='scheduled',
            created_at=now
        )
        db.add(db_session)
    
    # 5. Finalize main transaction BEFORE calling LLM
    run.completed_at = datetime.now()
    run.status = 'success' if scheduled_sessions else 'failed'
    if not scheduled_sessions and solver_tasks:
        run.infeasible_reason = "No valid schedule found by solver"
    
    db.commit()
    print("DEBUG: Committed results")
    
    # 6. Notify Frontend (Early Refresh)
    try:
        from app.core.ws_manager import manager
        manager.publish_broadcast_sync("REFRESH")
        print("DEBUG: Sent REFRESH signal")
    except Exception as e:
        print(f"WS Notify failed: {e}")

    # 7. Enqueue Explanation (SLOW, OPTIONAL)
    # We use a separate job so it doesn't timeout the main one
    try:
        from app.workers.queue import queue
        queue.enqueue(
            "app.services.scheduling_service.generate_explanation_background",
            job_id=f"explain_{run.id}",
            user_id="user_1",
            solver_tasks=solver_tasks,
            scheduled_sessions=scheduled_sessions,
            job_timeout=300
        )
        print("DEBUG: Enqueued explanation job")
    except Exception as e:
        print(f"Failed to enqueue explanation: {e}")

    return len(scheduled_sessions)

def generate_explanation_background(user_id: str, solver_tasks: List[SolverTask], scheduled_sessions: List[ScheduledSession]):
    """Slow LLM task that runs independently."""
    from app.core.database import SessionLocal
    from app.models.preferences import UserPreferences as PreferencesModel
    from app.services.llm.gemini import generate_schedule_explanation
    
    db = SessionLocal()
    try:
        explanation = generate_schedule_explanation(solver_tasks, scheduled_sessions)
        prefs_db = db.query(PreferencesModel).filter(PreferencesModel.user_id == user_id).first()
        if prefs_db:
            prefs_db.last_schedule_explanation = explanation
            db.commit()
            
            # Notify AGAIN so coach text updates
            from app.core.ws_manager import manager
            manager.publish_broadcast_sync("REFRESH")
    except Exception as e:
        print(f"Error generating background explanation: {e}")
    finally:
        db.close()
