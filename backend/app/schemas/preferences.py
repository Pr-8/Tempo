from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class UserPreferencesBase(BaseModel):
    available_start_hour: int = Field(ge=0, le=23)
    available_end_hour: int = Field(ge=0, le=23)
    available_days: List[int] = Field(description="List of weekdays (0-6) where user is available")
    min_session_minutes: int = Field(gt=0)
    max_session_minutes: int = Field(gt=0)
    max_sessions_per_day: int = Field(gt=0)
    min_break_minutes: int = Field(ge=0)
    planning_horizon_days: int = Field(gt=0, default=21)
    blocked_dates: str = ""
    last_schedule_explanation: Optional[str] = None

class UserPreferencesUpdate(UserPreferencesBase):
    pass

class UserPreferences(UserPreferencesBase):
    updated_at: datetime

    class ConfigDict:
        from_attributes = True

UserPreferences.model_rebuild()
