from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List

from db import get_db
from models import Task, ScheduledSession
from ws_manager import manager
import asyncio

router = APIRouter(prefix="/sessions")
HARDCODED_USER_ID = "user_1"

def row_to_dict(row):
    d = {}
    for c in row.__table__.columns:
        val = getattr(row, c.name)
        if isinstance(val, (date, datetime)):
            d[c.name] = val.isoformat()
        else:
            d[c.name] = val
    return d

@router.get("/")
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(ScheduledSession).filter(
        ScheduledSession.status == "pending"
    ).order_by(ScheduledSession.start_time).all()
    return [row_to_dict(s) for s in sessions]

@router.patch("/{session_id}/complete")
def mark_complete(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScheduledSession).filter(ScheduledSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    task_id = session.task_id
    session_start = session.start_time
    
    # 1. Find all sessions for this task that are at or before this session
    sessions_to_delete = db.query(ScheduledSession).filter(
        ScheduledSession.task_id == task_id,
        ScheduledSession.start_time <= session_start,
        ScheduledSession.status == "pending"
    ).all()
    
    total_minutes_completed = 0
    for s in sessions_to_delete:
        if s.start_time and s.end_time:
            duration = s.end_time - s.start_time
            total_minutes_completed += duration.total_seconds() / 60
    
    # 2. Update the parent Task's estimated hours
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        completed_hrs = total_minutes_completed / 60.0
        task.estimated_hours = max(0.0, task.estimated_hours - completed_hrs)
        if task.estimated_hours <= 0:
            task.status = "complete"
        db.commit()

    # 4. Delete the sessions
    for s in sessions_to_delete:
        db.delete(s)
    db.commit()
    
    # Broadcast refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass
            
    return {"ok": True, "remaining_hours": task.estimated_hours if task else 0}

@router.patch("/{session_id}/failed")
def mark_failed(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScheduledSession).filter(ScheduledSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.status = "failed"
    session.failed_at = datetime.utcnow()
    db.commit()
    
    # Broadcast refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass
    
    return {"ok": True, "message": "Marked failed. Click 'Reschedule' to update calendar."}

@router.post("/reschedule")
def manual_reschedule(db: Session = Depends(get_db)):
    """Explicitly triggers the scheduling pipeline."""
    from jobs.reschedule import run_reschedule_pipeline
    result = run_reschedule_pipeline(HARDCODED_USER_ID)
    
    # Broadcast refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass
        
    return result
