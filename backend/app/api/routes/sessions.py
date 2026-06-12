from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List

from app.core.database import get_db
from app.models.session import Session as SessionModel
from app.models.task import Task as TaskModel
from app.schemas.session import Session, SessionActionResponse
from app.workers.queue import enqueue_regeneration

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/", response_model=List[Session])
def read_sessions(db: Session = Depends(get_db)):
    return db.query(SessionModel).all()

@router.get("/week", response_model=List[Session])
def read_sessions_week(start_date: datetime, db: Session = Depends(get_db)):
    end_date = start_date + timedelta(days=7)
    return db.query(SessionModel).filter(
        SessionModel.start_time >= start_date,
        SessionModel.start_time < end_date
    ).all()

@router.patch("/{session_id}/complete", response_model=SessionActionResponse)
def complete_session(session_id: UUID, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not db_session:
        # Check if maybe it was replaced by a regeneration?
        # This is a bit complex, let's at least handle the error better.
        raise HTTPException(status_code=404, detail="Session not found. It may have been updated by a background task. Please refresh.")
    
    if db_session.status == "completed":
        # Already done, return success (Idempotent)
        db_task = db.query(TaskModel).filter(TaskModel.id == db_session.task_id).first()
        return {
            "status": "completed",
            "task_status": db_task.status if db_task else "unknown",
            "remaining_hours": db_task.remaining_hours if db_task else 0
        }

    if db_session.status != "scheduled":
        raise HTTPException(status_code=400, detail=f"Session already {db_session.status}")

    try:
        db_session.status = "completed"
        
        # Update Task
        db_task = db.query(TaskModel).filter(TaskModel.id == db_session.task_id).first()
        if db_task:
            reduction_hours = db_session.duration_minutes / 60.0
            db_task.remaining_hours = max(0, db_task.remaining_hours - reduction_hours)
            
            if db_task.remaining_hours <= 0:
                db_task.status = "complete"
            else:
                db_task.status = "in_progress"
            db_task.updated_at = datetime.now()

        db.commit()
        if db_task: db.refresh(db_task)
        enqueue_regeneration()
        
        return {
            "status": "completed",
            "task_status": db_task.status if db_task else "unknown",
            "remaining_hours": db_task.remaining_hours if db_task else 0
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to complete session: {str(e)}")

@router.patch("/{session_id}/failed", response_model=SessionActionResponse)
def fail_session(session_id: UUID, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found. It may have been updated by a background task. Please refresh.")
    
    if db_session.status == "failed":
        # Already failed, return success (Idempotent)
        db_task = db.query(TaskModel).filter(TaskModel.id == db_session.task_id).first()
        return {
            "status": "failed",
            "task_status": db_task.status if db_task else "unknown",
            "remaining_hours": db_task.remaining_hours if db_task else 0
        }

    if db_session.status != "scheduled":
        raise HTTPException(status_code=400, detail=f"Session already {db_session.status}")

    try:
        db_session.status = "failed"
        
        db_task = db.query(TaskModel).filter(TaskModel.id == db_session.task_id).first()
        if db_task:
            db_task.status = "in_progress" # ensure it's not 'pending' if we failed a session
            db_task.updated_at = datetime.now()

        db.commit()
        if db_task: db.refresh(db_task)
        enqueue_regeneration()
        
        return {
            "status": "failed",
            "task_status": db_task.status if db_task else "unknown",
            "remaining_hours": db_task.remaining_hours if db_task else 0
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark session failed: {str(e)}")

@router.post("/reschedule")
def reschedule_sessions():
    enqueue_regeneration()
    return {"status": "enqueued"}
