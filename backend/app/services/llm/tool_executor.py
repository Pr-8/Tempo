import json
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.core.database import SessionLocal
from app.models.task import Task
from app.models.session import Session
from app.models.preferences import UserPreferences
from app.models.memory import UserMemory
from app.services.llm.embedding import get_embedding

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

def find_task_by_title(db, title: str, include_completed: bool = False):
    """
    Finds a task by title using case-insensitive match (exact then partial).
    Returns (task, error_message).
    """
    query = db.query(Task)
    if not include_completed:
        query = query.filter(Task.status != "completed")
    
    # 1. Try exact match
    exact_tasks = query.filter(Task.title.ilike(title)).all()
    if len(exact_tasks) == 1:
        return exact_tasks[0], None
    
    # 2. Try partial/contains match
    contains_tasks = query.filter(Task.title.ilike(f"%{title}%")).all()
    if len(contains_tasks) == 1:
        return contains_tasks[0], None
    elif len(contains_tasks) > 1:
        titles_str = ", ".join([f"'{t.title}'" for t in contains_tasks])
        return None, f"Multiple tasks match '{title}': {titles_str}. Please be more specific."
    else:
        return None, f"No task found matching '{title}'."

def handle_get_tasks(db, args: Dict[str, Any]) -> str:
    status_filter = args.get("status_filter")
    
    query = db.query(Task)
    if status_filter == "completed":
        query = query.filter(Task.status == "completed")
    elif status_filter == "pending":
        query = query.filter(Task.status == "pending")
    elif status_filter == "in_progress":
        query = query.filter(Task.status == "in_progress")
    elif status_filter == "all":
        pass  # no filter
    else:
        # Default: return non-completed tasks
        query = query.filter(Task.status != "completed")
        
    tasks = query.order_by(Task.deadline.asc()).all()
    if not tasks:
        return "No tasks found."
        
    lines = []
    priority_labels = {1: "low", 2: "low-medium", 3: "medium", 4: "medium-high", 5: "high"}
    
    for t in tasks:
        priority_label = priority_labels.get(t.priority, f"priority-{t.priority}")
        type_str = "Fixed" if t.is_fixed else "Flexible"
        deadline_str = t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else "No deadline"
        lines.append(
            f"- [{t.status}] {t.title} | Course: {t.course} | Priority: {priority_label} | "
            f"Deadline: {deadline_str} | Remaining: {t.remaining_hours}h / {t.estimated_hours}h | Type: {type_str}"
        )
    return "Tasks:\n" + "\n".join(lines)

def handle_update_task(db, args: Dict[str, Any]) -> str:
    task_title = args.get("task_title")
    if not task_title:
        return "Error: task_title is required."
        
    task, err = find_task_by_title(db, task_title, include_completed=True)
    if err:
        return err
        
    if task.status == "completed":
        return f"Error: Task '{task.title}' is already completed and cannot be updated."
        
    changes = []
    
    # 1. Update Title
    new_title = args.get("new_title")
    if new_title:
        task.title = new_title
        changes.append(f"title to '{new_title}'")
        
    # 2. Update Course
    new_course = args.get("new_course")
    if new_course:
        task.course = new_course
        changes.append(f"course to '{new_course}'")
        
    # 3. Update Priority
    new_priority = args.get("new_priority")
    if new_priority:
        priority_val = PRIORITY_MAP.get(new_priority)
        if priority_val:
            task.priority = priority_val
            changes.append(f"priority to '{new_priority}'")
            
    # 4. Update Deadline
    new_deadline = args.get("new_deadline")
    if new_deadline:
        if task.is_fixed:
            return f"Error: Cannot change deadline for fixed event '{task.title}'."
        try:
            deadline = datetime.fromisoformat(new_deadline.replace("Z", ""))
            if len(new_deadline) <= 10:
                deadline = deadline.replace(hour=23, minute=59, second=59)
            if deadline < datetime.now():
                return f"Error: Deadline '{new_deadline}' must be in the future."
            task.deadline = deadline
            changes.append(f"deadline to '{deadline.strftime('%Y-%m-%d %H:%M')}'")
        except Exception as e:
            return f"Error parsing deadline: {e}"
            
    # 5. Update Estimated Hours
    new_estimated_hours = args.get("new_estimated_hours")
    if new_estimated_hours is not None:
        if task.is_fixed:
            return f"Error: Cannot change estimated hours for fixed event '{task.title}'."
        if new_estimated_hours <= 0:
            return "Error: estimated_hours must be greater than 0."
            
        old_est = task.estimated_hours
        task.estimated_hours = new_estimated_hours
        
        # Adjust remaining_hours proportionally
        if old_est > 0:
            ratio = new_estimated_hours / old_est
            task.remaining_hours = min(new_estimated_hours, task.remaining_hours * ratio)
            
        changes.append(f"estimated hours to {new_estimated_hours}h (remaining hours adjusted to {task.remaining_hours:.1f}h)")
        
    if not changes:
        return f"No changes requested for task '{task.title}'."
        
    task.updated_at = datetime.now()
    db.commit()
    enqueue_regeneration()
    return f"Updated task '{task.title}': " + ", ".join(changes) + "."

def handle_complete_task(db, args: Dict[str, Any]) -> str:
    task_title = args.get("task_title")
    if not task_title:
        return "Error: task_title is required."
        
    task, err = find_task_by_title(db, task_title, include_completed=False)
    if err:
        return err
        
    task.status = "completed"
    task.remaining_hours = 0
    task.updated_at = datetime.now()
    
    # Delete future scheduled sessions
    deleted_sessions = db.query(Session).filter(
        Session.task_id == task.id,
        Session.start_time >= datetime.now(),
        Session.status == "scheduled"
    ).delete()
    
    db.commit()
    enqueue_regeneration()
    return f"Marked task '{task.title}' as completed. Removed {deleted_sessions} future scheduled sessions."

def handle_delete_task(db, args: Dict[str, Any]) -> str:
    task_title = args.get("task_title")
    if not task_title:
        return "Error: task_title is required."
        
    task, err = find_task_by_title(db, task_title, include_completed=True)
    if err:
        return err
        
    title = task.title
    # Manually delete related sessions to prevent FK constraint issues
    db.query(Session).filter(Session.task_id == task.id).delete()
    db.delete(task)
    db.commit()
    enqueue_regeneration()
    return f"Deleted task '{title}' and all its associated sessions."

def handle_log_progress(db, args: Dict[str, Any]) -> str:
    task_title = args.get("task_title")
    hours_completed = args.get("hours_completed")
    
    if not task_title or hours_completed is None:
        return "Error: task_title and hours_completed are required."
        
    try:
        hours_completed = float(hours_completed)
    except ValueError:
        return f"Error: hours_completed must be a number, got '{hours_completed}'."
        
    if hours_completed <= 0:
        return "Error: hours_completed must be greater than 0."
        
    task, err = find_task_by_title(db, task_title, include_completed=False)
    if err:
        return err
        
    if task.is_fixed:
        return f"Error: Cannot log study progress on a fixed event '{task.title}'."
        
    new_remaining = max(0.0, task.remaining_hours - hours_completed)
    status_change = ""
    task.remaining_hours = new_remaining
    
    if task.status == "pending":
        task.status = "in_progress"
        status_change = " (status changed to in_progress)"
        
    if new_remaining == 0.0:
        task.status = "completed"
        # Delete future scheduled sessions
        deleted_sessions = db.query(Session).filter(
            Session.task_id == task.id,
            Session.start_time >= datetime.now(),
            Session.status == "scheduled"
        ).delete()
        status_change = f" (task marked as completed! 🎉 Removed {deleted_sessions} future scheduled sessions)"
        
    task.updated_at = datetime.now()
    db.commit()
    enqueue_regeneration()
    
    return f"Logged {hours_completed}h on task '{task.title}'{status_change}. Remaining: {new_remaining:.1f}h / {task.estimated_hours}h."

def handle_get_memories(db, args: Dict[str, Any]) -> str:
    query = args.get("query")
    limit = args.get("limit", 20)
    
    if query:
        query_embedding = get_embedding(query)
        if query_embedding is not None:
            memories = db.query(UserMemory).filter(
                UserMemory.user_id == HARDCODED_USER_ID,
                UserMemory.embedding.isnot(None)
            ).order_by(
                UserMemory.embedding.cosine_distance(query_embedding)
            ).limit(limit).all()
            
            unembedded = db.query(UserMemory).filter(
                UserMemory.user_id == HARDCODED_USER_ID,
                UserMemory.embedding.is_(None)
            ).all()
            
            all_memories = memories + unembedded
        else:
            all_memories = db.query(UserMemory).filter(
                UserMemory.user_id == HARDCODED_USER_ID
            ).order_by(UserMemory.created_at.desc()).limit(limit).all()
    else:
        all_memories = db.query(UserMemory).filter(
            UserMemory.user_id == HARDCODED_USER_ID
        ).order_by(UserMemory.created_at.desc()).limit(limit).all()
        
    if not all_memories:
        return "No memories stored yet."
        
    lines = []
    for m in all_memories[:limit]:
        date_str = m.created_at.strftime("%b %d, %Y")
        lines.append(f"- {m.content} (type: {m.memory_type}, remembered on {date_str})")
        
    return "Stored memories:\n" + "\n".join(lines)

def handle_reschedule(db, args: Dict[str, Any]) -> str:
    enqueue_regeneration()
    return "Schedule regeneration started in the background. The calendar should update in a few seconds."

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

        elif tool_name == "get_tasks":
            return handle_get_tasks(db, tool_args)

        elif tool_name == "update_task":
            return handle_update_task(db, tool_args)

        elif tool_name == "complete_task":
            return handle_complete_task(db, tool_args)

        elif tool_name == "delete_task":
            return handle_delete_task(db, tool_args)

        elif tool_name == "log_progress":
            return handle_log_progress(db, tool_args)

        elif tool_name == "get_memories":
            return handle_get_memories(db, tool_args)

        elif tool_name == "reschedule":
            return handle_reschedule(db, tool_args)

        return "Unknown tool."
    
    except Exception as e:
        db.rollback()
        return f"Error executing tool {tool_name}: {str(e)}"
    finally:
        db.close()
