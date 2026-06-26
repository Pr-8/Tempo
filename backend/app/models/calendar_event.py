import uuid
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, default="user_1")
    google_event_id = Column(String, unique=True, nullable=False)
    summary = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_all_day = Column(Boolean, nullable=False, default=False)
    source = Column(String, nullable=False, default="google")
    tempo_session_id = Column(UUID(as_uuid=True), nullable=True)
    synced_at = Column(DateTime, nullable=False)
