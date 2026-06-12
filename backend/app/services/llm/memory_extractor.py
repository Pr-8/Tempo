import json
import logging
from typing import List
from google import genai
from google.genai import types
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.memory import UserMemory
from .prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def extract_memories(user_id: str, message: str, existing_memories: List[str]):
    """
    Extract new facts from a user message and store them in the database.
    This runs as a background task and manages its own DB session.
    """
    if settings.GEMINI_API_KEY == "fallback":
        return

    db = SessionLocal()
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=10000,
            retry_options=types.HttpRetryOptions(attempts=1)
        )
    )
    
    prompt = f"Existing memories:\n" + "\n".join([f"- {m}" for m in existing_memories])
    prompt += f"\n\nNew message: {message}\n\nExtract new facts:"
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=[
                MEMORY_EXTRACTION_SYSTEM_PROMPT,
                prompt
            ],
            config={'response_mime_type': 'application/json'}
        )
        
        new_facts = json.loads(response.text)
        if not isinstance(new_facts, list):
            logger.warning(f"Expected a list of facts, got: {type(new_facts)}")
            return

        for fact in new_facts:
            # Simple deduplication
            if any(fact.lower() in m.lower() or m.lower() in fact.lower() for m in existing_memories):
                continue
                
            memory = UserMemory(
                user_id=user_id,
                content=fact,
                memory_type="context"
            )
            db.add(memory)
        
        db.commit()
        logger.info(f"Extracted {len(new_facts)} new memories for user {user_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Memory extraction failed: {str(e)}")
    finally:
        db.close()
