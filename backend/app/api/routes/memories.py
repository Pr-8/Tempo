from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.memory import UserMemory
from app.schemas.memory import MemoryResponse

router = APIRouter(prefix="/memories", tags=["memories"])

@router.get("/", response_model=List[MemoryResponse])
def get_memories(user_id: str = "user_1", db: Session = Depends(get_db)):
    """Fetch all memories for a specific user, sorted by creation date descending."""
    return db.query(UserMemory).filter(UserMemory.user_id == user_id).order_by(UserMemory.created_at.desc()).all()

@router.delete("/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    """Delete a single memory by ID."""
    memory = db.query(UserMemory).filter(UserMemory.id == memory_id).first()
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    db.delete(memory)
    db.commit()
    return {"status": "ok"}

@router.delete("/")
def delete_all_memories(user_id: str = "user_1", db: Session = Depends(get_db)):
    """Delete all memories for a user."""
    db.query(UserMemory).filter(UserMemory.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return {"status": "ok"}
