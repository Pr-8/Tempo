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
    now = datetime.now()
    
    for task in pending_tasks:
        # User Logic: "assume event done when it goes in the past"
        if task.is_fixed and task.fixed_end and task.fixed_end < now:
            task.status = "complete"
            db.commit()
            continue

        # 3. Use estimated_hours as remaining_hours
        # (We now subtract duration directly from estimated_hours when marking sessions done)
        remaining_hrs = round(task.estimated_hours, 2)
        
        # Standard tasks are not done unless marked done (status == "complete")
        # Fixed events are passed regardless of hours (if not in past)
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
