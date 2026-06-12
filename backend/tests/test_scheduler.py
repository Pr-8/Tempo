from app.services.solver.scheduler import TempoScheduler
from app.services.solver.models import SolverTask, SolverPreferences
from datetime import datetime, timedelta, timezone
import uuid

def test_basic_solve():
    now = datetime.now(timezone.utc)
    task = SolverTask(
        id=uuid.uuid4(),
        title="Math",
        course="Calculus",
        remaining_hours=2.0,
        deadline=now + timedelta(days=2),
        priority=5
    )
    prefs = SolverPreferences(
        available_start_hour=9,
        available_end_hour=17,
        available_days=[0, 1, 2, 3, 4, 5, 6],
        min_session_minutes=30,
        max_session_minutes=120,
        max_sessions_per_day=4,
        min_break_minutes=15,
        planning_horizon_days=7
    )
    
    scheduler = TempoScheduler([task], prefs, now)
    sessions = scheduler.solve()
    
    assert len(sessions) > 0
    # 2.0 hours = 120 minutes
    assert sum(s.duration_minutes for s in sessions) == 120
