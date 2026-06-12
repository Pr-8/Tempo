import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    course = Column(String, nullable=False)
    estimated_hours = Column(Float, nullable=False)
    remaining_hours = Column(Float, nullable=False)
    deadline = Column(DateTime, nullable=False)
    priority = Column(Integer, nullable=False, default=3)
    status = Column(String, nullable=False, default='pending')
    source = Column(String, nullable=False, default='manual')
    is_fixed = Column(Boolean, nullable=False, default=False)
    fixed_start = Column(DateTime, nullable=True)
    fixed_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_scheduled_at = Column(DateTime, nullable=True)
