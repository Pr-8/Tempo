import json
from typing import List
from google import genai
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.memory import UserMemory
from .prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT

def extract_memories(user_id: str, message: str, existing_memories: List[str], db: Session):
    """
    Extract new facts from a user message and store them in the database.
    """
    if settings.GEMINI_API_KEY == "fallback":
        return

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = f"Existing memories:\n" + "\n".join([f"- {m}" for m in existing_memories])
    prompt += f"\n\nNew message: {message}\n\nExtract new facts:"
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                MEMORY_EXTRACTION_SYSTEM_PROMPT,
                prompt
            ],
            config={'response_mime_type': 'application/json'}
        )
        
        # The new SDK response.text should be the JSON string if configured
        new_facts = json.loads(response.text)
        if not isinstance(new_facts, list):
            print(f"Expected a list of facts, got: {type(new_facts)}")
            return

        for fact in new_facts:
            # Simple deduplication: check if fact is already in existing_memories (case-insensitive)
            # Or if it's already in the database for this session
            if any(fact.lower() in m.lower() or m.lower() in fact.lower() for m in existing_memories):
                continue
                
            memory = UserMemory(
                user_id=user_id,
                content=fact,
                memory_type="context" # Default type
            )
            db.add(memory)
        
        db.commit()
    except Exception as e:
        print(f"Memory extraction failed: {e}")
