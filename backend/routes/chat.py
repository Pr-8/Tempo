import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from models import ChatMessage, UserMemory, UserPreferences
from llm.tools import TOOLS
from llm.tool_executor import execute_tool
from jobs.memory_extractor import extract_memories_from_message
from db import get_db, get_db_context
from ws_manager import manager
import asyncio

router = APIRouter(prefix="/chat")
HARDCODED_USER_ID = "user_1"

def build_chat_system_prompt(user_id: str) -> str:
    with get_db_context() as db:
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        
        # Fetch recent memories
        memories = db.query(UserMemory).filter_by(user_id=user_id).order_by(
            UserMemory.last_referenced_at.desc()
        ).limit(10).all()
        memory_text = "\n".join(f"- {m.content}" for m in memories) or "None yet."
        
        return f"""You are tempo, a helpful study scheduling assistant.
You help students manage their study schedules by adding tasks, 
moving sessions, blocking time, and answering questions about their plan.

CORE CONCEPTS:
- EVENTS (Fixed): These are anchors on the calendar (classes, meetings). 
  They have a start and end time. The AI NEVER moves them.
- TASKS (Flexible): These are work items (assignments, revision). 
  They have a duration and a deadline. The AI finds the best time for them.
  Users can manually place them (DRAFT), but the AI may move them during a RESCHEDULE.

IMPORTANT RULES:
- If a user mentions a new item, you MUST ask if it is an EVENT (fixed) or a TASK (flexible) 
  unless they have already made it clear. 
- Explain that Events never move, while Tasks can be automatically rescheduled.
- Always use the get_schedule tool before answering questions about 
  specific times or what is scheduled when.
- If information is missing to add a task/event, use ask_clarification. Ask ONE thing at a time.
- When the user mentions something that should be remembered 
  (e.g. a recurring commitment, a stated preference), acknowledge it naturally.
- Today's date is {datetime.utcnow().date().isoformat()}.

USER PREFERENCES:
- Working hours: {prefs.day_start} to {prefs.day_end}
- Available days: {prefs.available_days}
- Max sessions per day: {prefs.max_sessions_per_day}

THINGS TO REMEMBER ABOUT THIS USER:
{memory_text}
"""

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []   # [{role, content}]

@router.post("/")
def chat(body: ChatRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    system_prompt = build_chat_system_prompt(HARDCODED_USER_ID)
    
    # Convert tool definitions to Gemini format
    gemini_tools = [
        Tool(function_declarations=[
            FunctionDeclaration(
                name        = t["name"],
                description = t["description"],
                parameters  = t["parameters"]
            ) for t in TOOLS
        ])
    ]
    
    model = genai.GenerativeModel(
        model_name     = "gemini-flash-latest",
        system_instruction = system_prompt,
        tools          = gemini_tools
    )
    
    # Build message history for multi-turn context
    history = []
    if body.history:
        for h in body.history:
            role = "model" if h["role"] == "assistant" else h["role"]
            history.append({"role": role, "parts": [h["content"]]})
    
    chat_session = model.start_chat(history=history)
    
    # Send user message
    response = chat_session.send_message(body.message)
    
    # --- Agent loop ---
    max_iterations = 5
    tool_calls_log = []
    
    for _ in range(max_iterations):
        candidate = response.candidates[0]
        
        # Check if model wants to call a tool
        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call and part.function_call.name
        ]
        
        if not function_calls:
            # Model produced a final text response
            final_text = "".join(
                part.text for part in candidate.content.parts
                if part.text
            )
            break
        
        # Execute tool calls and feed results back
        tool_responses = []
        for fc in function_calls:
            result = execute_tool(fc.name, dict(fc.args))
            if isinstance(result, str):
                result = result.replace(" Schedule is being updated.", "")
            
            tool_calls_log.append({
                "tool":   fc.name,
                "args":   dict(fc.args),
                "result": result
            })
            
            tool_responses.append({
                "function_response": {
                    "name": fc.name,
                    "response": {"result": result}
                }
            })
        
        # Send tool results back to the model
        response = chat_session.send_message(tool_responses)
    else:
        final_text = "I'm having trouble completing that request. Could you rephrase?"
    
    # Persist messages to DB
    with get_db_context() as db:
        db.add(ChatMessage(
            role       = "user",
            content    = body.message,
            created_at = datetime.utcnow()
        ))
        db.add(ChatMessage(
            role       = "assistant",
            content    = final_text,
            tool_calls = json.dumps(tool_calls_log),
            created_at = datetime.utcnow()
        ))
        db.commit()
    
    # Trigger memory extraction
    try:
        extract_memories_from_message(body.message, HARDCODED_USER_ID)
    except Exception as e:
        print(f"DEBUG: Memory extraction failed: {e}")
    
    # Broadcast refresh
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast("REFRESH"))
    except Exception:
        pass
    
    return {
        "reply":      final_text,
        "tool_calls": tool_calls_log
    }
