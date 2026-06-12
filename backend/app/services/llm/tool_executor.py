import json
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.core.database import SessionLocal
from app.models.task import Task
from app.models.session import Session
from app.models.preferences import UserPreferences

from app.workers.queue import enqueue_regeneration

HARDCODED_USER_ID = "user_1"

PRIORITY_MAP = {
    "low": 1,
    "medium": 3,
    "high": 5
}

PREFERENCE_MAP = {
    "day_start": "available_start_hour",
    "day_end": "available_end_hour",
    "max_sessions_per_day": "max_sessions_per_day",
    "min_break_minutes": "min_break_minutes",
    "preferred_session_mins": "min_session_minutes",
    "max_session_mins": "max_session_minutes"
}

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool call and return a string result."""
    print(f"DEBUG: Executing tool {tool_name} with args {tool_args}")
    
    db = SessionLocal()
    try:
        if tool_name == "add_task":
            is_fixed = tool_args.get("is_fixed", False)
            title = tool_args["title"]
            priority_str = tool_args.get("priority", "medium")
            priority = PRIORITY_MAP.get(priority_str, 3)
            
            now = datetime.now()
            
            if is_fixed:
                f_start_str = tool_args.get("fixed_start")
                f_end_str = tool_args.get("fixed_end")
                if not f_start_str or not f_end_str:
                    return "Error: Events must have start and end times."
                f_start = datetime.fromisoformat(f_start_str.replace("Z", ""))
                f_end = datetime.fromisoformat(f_end_str.replace("Z", ""))
                duration = f_end - f_start
                est_hours = duration.total_seconds() / 3600
                deadline = f_end
            else:
                est_hours = tool_args.get("estimated_hours")
                deadline_str = tool_args.get("deadline")
                if not est_hours or not deadline_str:
                    return "Error: Tasks must have estimated hours and a deadline."
                deadline = datetime.fromisoformat(deadline_str.replace("Z", ""))
                # If only date was provided, set to end of day
                if len(deadline_str) <= 10:
                    deadline = deadline.replace(hour=23, minute=59, second=59)
                f_start = None
                f_end = None

            task = Task(
                id=uuid.uuid4(),
                title=title,
                course=tool_args.get("course", "General"),
                estimated_hours=est_hours,
                remaining_hours=est_hours,
                deadline=deadline,
                priority=priority,
                status="pending",
                source="chat",
                is_fixed=is_fixed,
                fixed_start=f_start,
                fixed_end=f_end,
                created_at=now,
                updated_at=now
            )
            db.add(task)
            db.flush() # To get the task ID if needed

            # Create session if fixed time provided
            if f_start and f_end:
                duration_mins = int((f_end - f_start).total_seconds() / 60)
                session = Session(
                    id=uuid.uuid4(),
                    task_id=task.id,
                    start_time=f_start,
                    end_time=f_end,
                    duration_minutes=duration_mins,
                    status="scheduled",
                    created_at=now
                )
                db.add(session)
            
            db.commit()
            enqueue_regeneration()
            type_str = "Event" if is_fixed else "Task"
            return f"{type_str} '{task.title}' added."

        elif tool_name == "block_time":
            prefs = db.query(UserPreferences).first() # Currently only one user supported
            if not prefs:
                return "User preferences not found."
            
            blocked = prefs.blocked_dates or ""
            blocked_list = [d.strip() for d in blocked.split(",") if d.strip()]
            date_to_block = tool_args["date"]
            if date_to_block not in blocked_list:
                blocked_list.append(date_to_block)
                prefs.blocked_dates = ",".join(blocked_list)
                prefs.updated_at = datetime.now()
                db.commit()
                enqueue_regeneration()
                return f"Blocked {date_to_block}."
            else:
                return f"{date_to_block} was already blocked."

        elif tool_name == "get_schedule":
            start_date_str = tool_args.get("start_date")
            end_date_str = tool_args.get("end_date")
            
            try:
                start = datetime.fromisoformat(start_date_str)
                end = datetime.fromisoformat(end_date_str)
                if len(end_date_str) <= 10:
                    end = end.replace(hour=23, minute=59, second=59)
            except Exception as e:
                return f"Error parsing dates: {e}"

            sessions = db.query(Session).filter(
                Session.start_time >= start,
                Session.start_time <= end
            ).order_by(Session.start_time).all()
            
            if not sessions:
                return f"No sessions scheduled between {start_date_str} and {end_date_str}."
            
            lines = []
            for s in sessions:
                task = db.query(Task).get(s.task_id)
                task_title = task.title if task else "Unknown Task"
                lines.append(
                    f"- {task_title}: {s.start_time.strftime('%a %b %d, %H:%M')} "
                    f"to {s.end_time.strftime('%H:%M')}"
                )
            return f"Current schedule from {start_date_str} to {end_date_str}:\n" + "\n".join(lines)

        elif tool_name == "update_preference":
            prefs = db.query(UserPreferences).first()
            if not prefs:
                return "User preferences not found."
            
            tool_key = tool_args["key"]
            value = tool_args["value"]
            
            model_key = PREFERENCE_MAP.get(tool_key)
            if not model_key:
                return f"Unknown preference key: {tool_key}"
            
            if hasattr(prefs, model_key):
                try:
                    # All these preferences are currently integers in the model
                    setattr(prefs, model_key, int(value))
                    prefs.updated_at = datetime.now()
                    db.commit()
                    enqueue_regeneration()
                    return f"Updated {tool_key} to {value}."
                except ValueError:
                    return f"Invalid value for {tool_key}: {value}. Expected an integer."
            else:
                return f"Model missing attribute: {model_key}"

        elif tool_name == "ask_clarification":
            return f"CLARIFICATION: {tool_args['question']}"

        return "Unknown tool."
    
    except Exception as e:
        db.rollback()
        return f"Error executing tool {tool_name}: {str(e)}"
    finally:
        db.close()
