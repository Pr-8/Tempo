import google.generativeai as genai
import json, os
from datetime import datetime
from models import UserMemory
from db import get_db_context

def extract_memories_from_message(message: str, user_id: str = "user_1"):
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-flash-latest")

    EXTRACTION_PROMPT = """
Extract any NEW persistent facts about the user from this message.
Return ONLY a JSON array. Return an empty array [] if there is nothing new.
Each fact should have: "content" (string), "type" ("constraint"|"preference"|"context").

Examples of things to extract:
- Recurring commitments: "I have football every Thursday at 7pm"
- Stated struggles: "I always find calculus hard"
- Personal preferences: "I prefer doing hard tasks in the morning"
- Life context: "I work part time on Saturdays"

Do NOT extract things that are already one-off task requests 
(those are handled separately). 
Return raw JSON only, no backticks, no explanation.
"""

    response = model.generate_content(
        EXTRACTION_PROMPT + f"\n\nUser message: \"{message}\""
    )
    
    text = response.text.strip()
    # Clean potential markdown backticks
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        facts = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"DEBUG: Memory extraction JSON error: {e}. Text: {text}")
        return
    
    if not facts:
        return
    
    with get_db_context() as db:
        existing = [m.content for m in db.query(UserMemory).filter_by(user_id=user_id).all()]
        
        for fact in facts:
            content = fact.get("content","").strip()
            if not content:
                continue
            
            # Simple dedup
            if any(content.lower() in e.lower() or e.lower() in content.lower()
                   for e in existing):
                continue
                
            db.add(UserMemory(
                user_id            = user_id,
                content            = content,
                memory_type        = fact.get("type", "context"),
                created_at         = datetime.utcnow(),
                last_referenced_at = datetime.utcnow()
            ))
        db.commit()
        print(f"DEBUG: Extracted {len(facts)} new memories")
