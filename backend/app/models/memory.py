import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class UserMemory(Base):
    __tablename__ = "user_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, default="user_1")
    content = Column(String, nullable=False)    # e.g., "User has football every Thursday at 7pm"
    memory_type = Column(String, nullable=False) # "constraint", "preference", "context"
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_referenced_at = Column(DateTime, nullable=False, default=datetime.now)
