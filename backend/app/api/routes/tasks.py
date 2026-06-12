from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.task import Task as TaskModel
from app.schemas.task import Task, TaskCreate, TaskUpdate

from app.workers.queue import enqueue_regeneration

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", response_model=Task)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    now = datetime.now()
    db_task = TaskModel(
        **task_in.model_dump(),
        remaining_hours=task_in.estimated_hours,
        created_at=now,
        updated_at=now
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    enqueue_regeneration()
    return db_task

@router.get("/", response_model=List[Task])
def read_tasks(db: Session = Depends(get_db)):
    return db.query(TaskModel).all()

@router.get("/{task_id}", response_model=Task)
def read_task(task_id: UUID, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: UUID, task_in: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = task_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    db_task.updated_at = datetime.now()
    db.commit()
    db.refresh(db_task)
    enqueue_regeneration()
    return db_task

@router.delete("/{task_id}")
def delete_task(task_id: UUID, db: Session = Depends(get_db)):
    db_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    enqueue_regeneration()
    return {"status": "ok"}
