from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from uuid import UUID

class SolverTask(BaseModel):
    id: UUID
    title: str
    course: str
    remaining_hours: float
    deadline: datetime
    priority: int
    is_fixed: bool = False
    fixed_start: Optional[datetime] = None
    fixed_end: Optional[datetime] = None

class SolverPreferences(BaseModel):
    available_start_hour: int
    available_end_hour: int
    available_days: List[int]
    blocked_dates: List[str] = [] # ISO format dates YYYY-MM-DD
    min_session_minutes: int
    max_session_minutes: int
    max_sessions_per_day: int
    min_break_minutes: int
    planning_horizon_days: int

class Slot(BaseModel):
    index: int
    dt: datetime
    is_preferred: bool

class ScheduledSession(BaseModel):
    task_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
