from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID

class TaskBase(BaseModel):
    title: str
    course: str
    estimated_hours: float = Field(gt=0)
    deadline: datetime
    priority: int = Field(ge=1, le=5, default=3)
    source: str = "manual"
    is_fixed: bool = False
    fixed_start: Optional[datetime] = None
    fixed_end: Optional[datetime] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    course: Optional[str] = None
    estimated_hours: Optional[float] = Field(None, gt=0)
    deadline: Optional[datetime] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None
    is_fixed: Optional[bool] = None
    fixed_start: Optional[datetime] = None
    fixed_end: Optional[datetime] = None

class Task(TaskBase):
    id: UUID
    remaining_hours: float
    status: str
    created_at: datetime
    updated_at: datetime
    last_scheduled_at: Optional[datetime] = None

    class ConfigDict:
        from_attributes = True
