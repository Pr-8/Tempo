from app.services.solver.scheduler import TempoScheduler
from app.services.solver.models import SolverTask, SolverPreferences, CalendarBlock
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

def test_calendar_blocking_solve():
    # 2026-06-26 is a Friday (weekday = 4)
    now = datetime(2026, 6, 26, 9, 0)
    task = SolverTask(
        id=uuid.uuid4(),
        title="Math",
        course="Calculus",
        remaining_hours=2.0,
        deadline=now + timedelta(days=1),
        priority=5
    )
    # Preferences: 9 AM to 1 PM (4 hours total, i.e. 8 slots)
    prefs = SolverPreferences(
        available_start_hour=9,
        available_end_hour=13,
        available_days=[4],
        min_session_minutes=30,
        max_session_minutes=120,
        max_sessions_per_day=4,
        min_break_minutes=15,
        planning_horizon_days=2
    )
    # Block 10:00 AM to 12:00 PM (2 hours) via Google Calendar
    block = CalendarBlock(
        start_time=datetime(2026, 6, 26, 10, 0),
        end_time=datetime(2026, 6, 26, 12, 0),
        summary="Doctor Appointment"
    )
    
    scheduler = TempoScheduler([task], prefs, now, calendar_blocks=[block])
    sessions = scheduler.solve()
    
    # Task requires 2 hours (120 mins). 
    # Total preferred hours: 9-13 (4 hours).
    # Blocked: 10-12 (2 hours).
    # Remaining available: 9-10 (1 hour) and 12-13 (1 hour).
    # Total available: 2 hours exactly.
    # The solver must schedule two 1-hour sessions (one at 9-10 and one at 12-13).
    assert len(sessions) == 2
    assert sum(s.duration_minutes for s in sessions) == 120
    
    # Assert they don't overlap with the block 10:00 - 12:00
    for s in sessions:
        assert s.start_time < datetime(2026, 6, 26, 10, 0) or s.start_time >= datetime(2026, 6, 26, 12, 0)
        assert s.end_time <= datetime(2026, 6, 26, 10, 0) or s.end_time > datetime(2026, 6, 26, 12, 0)
