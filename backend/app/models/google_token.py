from sqlalchemy import Column, String, Integer, DateTime, Boolean
from app.models.base import Base

class GoogleCalendarToken(Base):
    __tablename__ = "google_calendar_tokens"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False, default="user_1")
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=False)
    scopes = Column(String, nullable=False)
    calendar_id = Column(String, nullable=False, default="primary")
    sync_enabled = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
