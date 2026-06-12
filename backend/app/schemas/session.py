from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional

class SessionBase(BaseModel):
    task_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: str = "scheduled"

class Session(SessionBase):
    id: UUID
    created_at: datetime

    class ConfigDict:
        from_attributes = True

class SessionActionResponse(BaseModel):
    status: str
    task_status: str
    remaining_hours: float
