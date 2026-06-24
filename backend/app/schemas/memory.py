from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class MemoryResponse(BaseModel):
    id: UUID
    content: str
    memory_type: str
    created_at: datetime

    class ConfigDict:
        from_attributes = True
