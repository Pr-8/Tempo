import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, default="user_1", nullable=False)
    role = Column(String, nullable=False)     # "user", "assistant", "tool"
    content = Column(String, nullable=False)
    tool_calls = Column(String, nullable=True) # JSON-serialized list of tool calls
    created_at = Column(DateTime, nullable=False, default=datetime.now)
