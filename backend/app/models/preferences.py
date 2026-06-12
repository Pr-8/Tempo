from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False, default="user_1")
    available_start_hour = Column(Integer, nullable=False)
    available_end_hour = Column(Integer, nullable=False)
    available_days = Column(JSONB, nullable=False)
    min_session_minutes = Column(Integer, nullable=False)
    max_session_minutes = Column(Integer, nullable=False)
    max_sessions_per_day = Column(Integer, nullable=False)
    min_break_minutes = Column(Integer, nullable=False)
    planning_horizon_days = Column(Integer, nullable=False, default=21)
    blocked_dates = Column(String, nullable=False, default="")
    last_schedule_explanation = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False)
