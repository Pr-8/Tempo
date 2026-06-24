import logging
from typing import Optional, List
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_embedding(text: str) -> Optional[List[float]]:
    """Generate a 768-dim embedding using Gemini Embedding 2."""
    if settings.GEMINI_API_KEY == "fallback":
        return None
    
    try:
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=10000,
                retry_options=types.HttpRetryOptions(attempts=1)
            )
        )
        result = client.models.embed_content(
            model='gemini-embedding-2',
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=3072)
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        return None
