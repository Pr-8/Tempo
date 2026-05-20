import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Date, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    course = Column(String, nullable=True)
    estimated_hours = Column(Float, nullable=False)
    deadline = Column(Date, nullable=False)
    priority = Column(String, default="medium")  # medium, high, low
    status = Column(String, default="pending")    # pending, complete, failed
    source = Column(String, default="manual")    # manual, syllabus, lms, email
    created_at = Column(DateTime, default=datetime.utcnow)

    # Support for fixed events (meetings, classes)
    is_fixed = Column(Boolean, default=False)
    fixed_start = Column(DateTime, nullable=True)
    fixed_end = Column(DateTime, nullable=True)

    sessions = relationship("ScheduledSession", back_populates="task", cascade="all, delete-orphan")

class ScheduledSession(Base):
    __tablename__ = "scheduled_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="pending")    # pending, complete, failed
    failed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="sessions")

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False)
    available_days = Column(String, default="mon,tue,wed,thu,fri")
    day_start = Column(String, default="09:00")
    day_end = Column(String, default="18:00")
    max_sessions_per_day = Column(Integer, default=3)
    min_break_minutes = Column(Integer, default=30)
    preferred_session_mins = Column(Integer, default=60)
    max_session_mins = Column(Integer, default=120)
    schedule_dirty = Column(Boolean, default=False)
    blocked_dates = Column(String, default="")  # Comma-separated ISO dates
    last_schedule_explanation = Column(String, nullable=True)
