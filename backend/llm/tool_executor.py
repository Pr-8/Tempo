import json
from datetime import datetime, date, timedelta
from models import Task, ScheduledSession, UserPreferences
from jobs.reschedule import mark_schedule_dirty
from db import get_db_context

HARDCODED_USER_ID = "user_1"

def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool call and return a string result."""
    print(f"DEBUG: Executing tool {tool_name} with args {tool_args}")
    with get_db_context() as db:
        if tool_name == "add_task":
            is_fixed = tool_args.get("is_fixed", False)
            title = tool_args["title"]
            priority = tool_args.get("priority", "medium")
            
            if is_fixed:
                f_start_str = tool_args.get("fixed_start")
                f_end_str = tool_args.get("fixed_end")
                if not f_start_str or not f_end_str:
                    return "Error: Events must have start and end times."
                f_start = datetime.fromisoformat(f_start_str.replace("Z", ""))
                f_end = datetime.fromisoformat(f_end_str.replace("Z", ""))
                duration = f_end - f_start
                est_hours = duration.total_seconds() / 3600
                deadline = f_end.date()
            else:
                est_hours = tool_args.get("estimated_hours")
                deadline_str = tool_args.get("deadline")
                if not est_hours or not deadline_str:
                    return "Error: Tasks must have estimated hours and a deadline."
                deadline = date.fromisoformat(deadline_str)
                f_start = datetime.fromisoformat(tool_args["fixed_start"].replace("Z", "")) if tool_args.get("fixed_start") else None
                f_end = datetime.fromisoformat(tool_args["fixed_end"].replace("Z", "")) if tool_args.get("fixed_end") else None

            task = Task(
                title           = title,
                course          = tool_args.get("course"),
                estimated_hours = est_hours,
                deadline        = deadline,
                priority        = priority,
                status          = "pending",
                source          = "chat",
                created_at      = datetime.utcnow(),
                is_fixed        = is_fixed,
                fixed_start     = f_start if is_fixed else None, # Only store permanently if fixed
                fixed_end       = f_end if is_fixed else None
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            # Create draft session if time provided
            if f_start and f_end:
                session = ScheduledSession(
                    task_id=task.id,
                    start_time=f_start,
                    end_time=f_end,
                    status="pending"
                )
                db.add(session)
                db.commit()

            type_str = "Event" if is_fixed else "Task"
            return f"{type_str} '{task.title}' added."

        elif tool_name == "block_time":
            prefs = db.query(UserPreferences).filter_by(
                user_id=HARDCODED_USER_ID
            ).first()
            if not prefs:
                return "User preferences not found."
            
            blocked = prefs.blocked_dates or ""
            blocked_list = [d.strip() for d in blocked.split(",") if d.strip()]
            if tool_args["date"] not in blocked_list:
                blocked_list.append(tool_args["date"])
                prefs.blocked_dates = ",".join(blocked_list)
                db.commit()
            return f"Blocked {tool_args['date']}."

        elif tool_name == "get_schedule":
            # Handle start/end date range
            start_date_str = tool_args.get("start_date")
            end_date_str = tool_args.get("end_date")
            
            try:
                start = datetime.fromisoformat(start_date_str)
                end = datetime.fromisoformat(end_date_str)
                # If only date was provided (no time), adjust end to end of day
                if len(end_date_str) <= 10:
                    end = end.replace(hour=23, minute=59, second=59)
            except Exception as e:
                return f"Error parsing dates: {e}"

            sessions = db.query(ScheduledSession).filter(
                ScheduledSession.start_time >= start,
                ScheduledSession.start_time <= end,
                ScheduledSession.status == "pending"
            ).order_by(ScheduledSession.start_time).all()
            
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
            prefs = db.query(UserPreferences).filter_by(
                user_id=HARDCODED_USER_ID
            ).first()
            if not prefs:
                return "User preferences not found."
            
            key = tool_args["key"]
            value = tool_args["value"]
            
            if hasattr(prefs, key):
                # Handle type conversion for integer fields
                if key in ["max_sessions_per_day", "min_break_minutes", "preferred_session_mins", "max_session_mins"]:
                    try:
                        setattr(prefs, key, int(value))
                    except ValueError:
                        return f"Invalid value for {key}: {value}. Expected an integer."
                else:
                    setattr(prefs, key, value)
                
                db.commit()
                return f"Updated {key} to {value}."
            else:
                return f"Unknown preference key: {key}"

        elif tool_name == "ask_clarification":
            return f"CLARIFICATION:{tool_args['question']}"

        elif tool_name == "move_session":
            session = db.query(ScheduledSession).get(tool_args["session_id"])
            if not session:
                return "Session not found."
            
            try:
                new_start = datetime.fromisoformat(tool_args["new_start_time"].replace("Z", ""))
                duration = session.end_time - session.start_time
                session.start_time = new_start
                session.end_time = new_start + duration
                db.commit()
                return f"Session moved to {new_start.strftime('%a %b %d at %H:%M')}."
            except Exception as e:
                return f"Error moving session: {e}"

        return "Unknown tool."
