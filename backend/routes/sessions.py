from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List

from db import get_db
from models import Task, ScheduledSession
from jobs.reschedule import mark_schedule_dirty

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
    
    session.status = "complete"
    db.commit()
    
    # Check if all sessions for this task are complete
    pending_count = db.query(ScheduledSession).filter(
        ScheduledSession.task_id == session.task_id,
        ScheduledSession.status == "pending"
    ).count()
    
    if pending_count == 0:
        task = db.query(Task).filter(Task.id == session.task_id).first()
        if task:
            task.status = "complete"
            db.commit()
            
    return {"ok": True}

@router.patch("/{session_id}/failed")
def mark_failed(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScheduledSession).filter(ScheduledSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.status = "failed"
    session.failed_at = datetime.utcnow()
    db.commit()
    
    mark_schedule_dirty(HARDCODED_USER_ID)
    
    return {"ok": True, "message": "Rescheduling..."}
