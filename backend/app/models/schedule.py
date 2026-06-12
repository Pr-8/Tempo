import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class ScheduleRun(Base):
    __tablename__ = "schedule_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    infeasible_reason = Column(String, nullable=True)
