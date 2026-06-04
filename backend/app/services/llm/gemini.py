from google import genai
from app.core.config import settings
from .prompts import EXPLANATION_PROMPT_SYSTEM, build_explanation_prompt

def generate_schedule_explanation(tasks: list, sessions: list) -> str:
    if settings.GEMINI_API_KEY == "fallback":
        return "Your schedule has been updated. (Gemini API key not configured)"

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    tasks_str = "\n".join([f"- {t.title} ({t.course}): {t.remaining_hours}h left, due {t.deadline}" for t in tasks])
    sessions_str = "\n".join([f"- {s.start_time.strftime('%Y-%m-%d %H:%M')}: {s.duration_minutes}m of {s.task_id}" for s in sessions])
    
    prompt = build_explanation_prompt(tasks_str, sessions_str)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                EXPLANATION_PROMPT_SYSTEM,
                prompt
            ]
        )
        return response.text
    except Exception as e:
        return f"Your schedule has been updated. (Explanation generation failed: {str(e)})"
