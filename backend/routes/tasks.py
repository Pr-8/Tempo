from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional

from db import get_db
from models import Task, UserPreferences
from jobs.reschedule import mark_schedule_dirty

router = APIRouter(prefix="/tasks")
HARDCODED_USER_ID = "user_1"

class TaskCreate(BaseModel):
    title: str
    course: Optional[str] = None
    estimated_hours: float
    deadline: date
    priority: str = "medium"

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
    if body.estimated_hours <= 0 or body.estimated_hours > 40:
        raise HTTPException(status_code=400, detail="estimated_hours must be between 0 and 40")
    if body.deadline <= date.today():
        raise HTTPException(status_code=400, detail="deadline must be in the future")
    
    task = Task(
        title=body.title,
        course=body.course,
        estimated_hours=body.estimated_hours,
        deadline=body.deadline,
        priority=body.priority,
        status="pending",
        source="manual",
        created_at=datetime.utcnow()
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    mark_schedule_dirty(HARDCODED_USER_ID)
    
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
    
    mark_schedule_dirty(HARDCODED_USER_ID)
    
    return {"ok": True}
