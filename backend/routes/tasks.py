from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional

from db import get_db
from models import Task, UserPreferences
from ws_manager import manager
import asyncio

router = APIRouter(prefix="/tasks")
HARDCODED_USER_ID = "user_1"

class TaskCreate(BaseModel):
    title: str
    course: Optional[str] = None
    estimated_hours: Optional[float] = None
    deadline: Optional[date] = None
    priority: str = "medium"
    is_fixed: bool = False
    fixed_start: Optional[datetime] = None
    fixed_end: Optional[datetime] = None

def row_to_dict(row):
    d = {}
    for c in row.__table__.columns:
        val = getattr(row, c.name)
        if isinstance(val, (date, datetime)):
            d[c.name] = val.isoformat()
        else:
            d[c.name] = val
    return d

@router.post("/")
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    if body.is_fixed:
        if not body.fixed_start or not body.fixed_end:
            raise HTTPException(status_code=400, detail="Events must have start and end times")
        # For events, estimated_hours is the duration
        duration = body.fixed_end - body.fixed_start
        est_hours = duration.total_seconds() / 3600
        deadline = body.fixed_end.date()
    else:
        if not body.estimated_hours or not body.deadline:
            raise HTTPException(status_code=400, detail="Tasks must have estimated hours and a deadline")
        if body.estimated_hours <= 0 or body.estimated_hours > 40:
            raise HTTPException(status_code=400, detail="estimated_hours must be between 0 and 40")
        if body.deadline < date.today():
            raise HTTPException(status_code=400, detail="deadline must be in the future (or today)")
        est_hours = body.estimated_hours
        deadline = body.deadline
    
    task = Task(
        title=body.title,
        course=body.course,
        estimated_hours=est_hours,
        deadline=deadline,
        priority=body.priority,
        status="pending",
        source="manual",
        created_at=datetime.utcnow(),
        is_fixed=body.is_fixed,
        fixed_start=body.fixed_start if body.is_fixed else None,
        fixed_end=body.fixed_end if body.is_fixed else None
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # DRAFT TIME FEATURE: If the user provided a time (even for a flexible task), 
    # create a scheduled session immediately so it shows on the UI.
    if body.fixed_start and body.fixed_end:
        from models import ScheduledSession
        session = ScheduledSession(
            task_id=task.id,
            start_time=body.fixed_start,
            end_time=body.fixed_end,
            status="pending"
        )
        db.add(session)
        db.commit()

    # Trigger real-time UI refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass

    return row_to_dict(task)

@router.get("/")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.deadline).all()
    return [row_to_dict(t) for t in tasks]

@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    # Trigger real-time UI refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass

    return {"ok": True}
