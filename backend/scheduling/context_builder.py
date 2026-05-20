from sqlalchemy.orm import Session
from models import Task, ScheduledSession, UserPreferences
from datetime import datetime

def build_scheduling_request(user_id: str, db: Session) -> dict:
    # 1. Query UserPreferences
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        raise ValueError(f"User preferences not found for user_id: {user_id}")

    # 2. Query all Tasks with status == "pending"
    pending_tasks = db.query(Task).filter(Task.status == "pending").all()
    
    solver_tasks = []
    
    for task in pending_tasks:
        # 3. Compute remaining_hours
        # Query ScheduledSession for that task_id where status == "complete"
        completed_sessions = db.query(ScheduledSession).filter(
            ScheduledSession.task_id == task.id,
            ScheduledSession.status == "complete"
        ).all()
        
        completed_mins = 0
        for s in completed_sessions:
            if s.start_time and s.end_time:
                duration = s.end_time - s.start_time
                completed_mins += duration.total_seconds() / 60
        
        remaining_hrs = max(0.0, task.estimated_hours - (completed_mins / 60.0))
        remaining_hrs = round(remaining_hrs, 2)
        
        # Skip the task if remaining_hrs <= 0 and it's not a fixed event
        # Fixed events should be passed regardless of "hours" if they are in the horizon
        if not task.is_fixed and remaining_hrs <= 0:
            continue
            
        task_data = {
            "id": task.id,
            "title": task.title,
            "remaining_hours": remaining_hrs,
            "deadline": task.deadline.isoformat(),
            "priority": task.priority,
            "is_fixed": task.is_fixed
        }
        
        if task.is_fixed:
            task_data["fixed_start"] = task.fixed_start.isoformat() if task.fixed_start else None
            task_data["fixed_end"] = task.fixed_end.isoformat() if task.fixed_end else None
            
        solver_tasks.append(task_data)

    # 4. Build and return the SchedulingRequest dict
    blocked_dates = [d.strip() for d in prefs.blocked_dates.split(",") if d.strip()]
    
    request = {
        "planning_horizon_days": 21,
        "tasks": solver_tasks,
        "constraints": {
            "available_windows": [
                {
                    "days": [d.strip() for d in prefs.available_days.split(",") if d.strip()],
                    "start": prefs.day_start,
                    "end": prefs.day_end
                }
            ],
            "blocked_dates": blocked_dates,
            "session_rules": {
                "min_session_minutes": 45,
                "max_session_minutes": prefs.max_session_mins,
                "preferred_session_minutes": prefs.preferred_session_mins,
                "min_break_between_sessions": prefs.min_break_minutes,
                "max_sessions_per_day": prefs.max_sessions_per_day
            }
        }
    }
    
    return request
