from app.services.llm.gemini import generate_schedule_explanation
from app.services.solver.models import SolverTask, ScheduledSession
from app.core.config import settings
from datetime import datetime, timedelta, timezone
import uuid

def test_explanation_fallback():
    # Force fallback mode
    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "fallback"
    
    try:
        task = SolverTask(
            id=uuid.uuid4(),
            title="Test Task",
            course="Test Course",
            remaining_hours=1.0,
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            priority=3
        )
        session = ScheduledSession(
            task_id=task.id,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_minutes=60
        )
        
        explanation = generate_schedule_explanation([task], [session])
        assert "updated" in explanation.lower()
        assert "Gemini API key not configured" in explanation
    finally:
        settings.GEMINI_API_KEY = original_key
