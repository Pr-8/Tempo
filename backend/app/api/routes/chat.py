from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.chat import ChatMessage
from app.models.memory import UserMemory
from app.models.preferences import UserPreferences
from app.services.llm.gemini import chat_with_tempo
from app.services.llm.memory_extractor import extract_memories

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    user_id: str = "user_1"

class ChatResponse(BaseModel):
    reply: str
    message_id: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 1. Fetch History (last 10 messages)
    history_objs = db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(10).all()
    # history_objs are in desc order, we want them in chronological order
    history = [{"role": h.role, "content": h.content} for h in reversed(history_objs)]
    
    # 2. Fetch Memories
    memories = db.query(UserMemory).filter(UserMemory.user_id == request.user_id).all()
    memory_texts = [m.content for m in memories]
    
    # 3. Fetch Preferences
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == request.user_id).first()
    pref_text = ""
    if prefs:
        pref_text = f"User Preferences: Work hours {prefs.work_hours_start}-{prefs.work_hours_end}, Focus {prefs.preferred_focus_duration}m."

    # 4. Build System Instruction
    system_instruction = f"""
You are Tempo, an AI study coordinator. You help students manage their schedules and tasks.
{pref_text}
User Memories:
""" + "\n".join([f"- {m}" for m in memory_texts]) + """

Be helpful, concise, and proactive. You can use tools to manage tasks and schedules.
"""

    # 5. Call LLM
    result = chat_with_tempo(request.message, history=history, system_instruction=system_instruction)
    
    # 6. Persist Messages
    user_msg = ChatMessage(role="user", content=request.message)
    asst_msg = ChatMessage(role="assistant", content=result["reply"])
    db.add(user_msg)
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)
    
    # 7. Background Memory Extraction
    background_tasks.add_task(extract_memories, request.user_id, request.message, memory_texts, db)
    
    return ChatResponse(reply=result["reply"], message_id=str(asst_msg.id))
