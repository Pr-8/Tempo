import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.services.solver.models import SolverTask, SolverPreferences
from app.services.solver.scheduler import TempoScheduler

def test_fixed_task_scheduling():
    current_time = datetime(2026, 6, 1, 8, 0) # Monday morning
    
    # Fixed task: Meeting from 10:00 to 11:00
    fixed_task = SolverTask(
        id=uuid4(),
        title="Fixed Meeting",
        course="Work",
        remaining_hours=1.0,
        deadline=current_time + timedelta(days=7),
        priority=1,
        is_fixed=True,
        fixed_start=current_time + timedelta(hours=2), # 10:00
        fixed_end=current_time + timedelta(hours=3)    # 11:00
    )
    
    # Flexible task: Study for 2 hours
    flex_task = SolverTask(
        id=uuid4(),
        title="Flex Study",
        course="CS101",
        remaining_hours=2.0,
        deadline=current_time + timedelta(days=1),
        priority=2
    )
    
    prefs = SolverPreferences(
        available_start_hour=9,
        available_end_hour=17,
        available_days=[0, 1, 2, 3, 4], # Mon-Fri
        min_session_minutes=30,
        max_session_minutes=120,
        max_sessions_per_day=3,
        min_break_minutes=30,
        planning_horizon_days=7
    )
    
    scheduler = TempoScheduler([fixed_task, flex_task], prefs, current_time)
    sessions = scheduler.solve()
    
    assert len(sessions) >= 2
    
    # Find fixed session
    fixed_sessions = [s for s in sessions if s.task_id == fixed_task.id]
    assert len(fixed_sessions) == 1
    assert fixed_sessions[0].start_time == current_time + timedelta(hours=2)
    
    # Ensure flex sessions don't overlap with fixed session
    fixed_start = fixed_sessions[0].start_time
    fixed_end = fixed_sessions[0].end_time
    
    for s in sessions:
        if s.task_id == flex_task.id:
            # Overlap check: (StartA < EndB) and (EndA > StartB)
            overlap = (s.start_time < fixed_end) and (s.end_time > fixed_start)
            assert not overlap, f"Flex session {s.start_time}-{s.end_time} overlaps with fixed {fixed_start}-{fixed_end}"

def test_blocked_dates():
    current_time = datetime(2026, 6, 1, 8, 0) # Monday
    blocked_date = "2026-06-02" # Tuesday is blocked
    
    task = SolverTask(
        id=uuid4(),
        title="Task",
        course="Course",
        remaining_hours=1.0,
        deadline=current_time + timedelta(days=3),
        priority=1
    )
    
    prefs = SolverPreferences(
        available_start_hour=9,
        available_end_hour=17,
        available_days=[0, 1, 2, 3, 4],
        blocked_dates=[blocked_date],
        min_session_minutes=30,
        max_session_minutes=120,
        max_sessions_per_day=3,
        min_break_minutes=30,
        planning_horizon_days=7
    )
    
    scheduler = TempoScheduler([task], prefs, current_time)
    sessions = scheduler.solve()
    
    for s in sessions:
        assert s.start_time.strftime("%Y-%m-%d") != blocked_date

def test_weekend_penalty():
    # If deadline is Sunday, and we have a choice between Monday and Saturday
    # The solver should prefer Monday (preferred day) unless it's full.
    current_time = datetime(2026, 6, 1, 8, 0) # Monday
    
    task = SolverTask(
        id=uuid4(),
        title="Weekday Preferred",
        course="Course",
        remaining_hours=1.0,
        deadline=current_time + timedelta(days=7),
        priority=1
    )
    
    prefs = SolverPreferences(
        available_start_hour=9,
        available_end_hour=17,
        available_days=[0], # ONLY MONDAY IS PREFERRED
        min_session_minutes=30,
        max_session_minutes=120,
        max_sessions_per_day=3,
        min_break_minutes=30,
        planning_horizon_days=7
    )
    
    scheduler = TempoScheduler([task], prefs, current_time)
    sessions = scheduler.solve()
    
    assert len(sessions) > 0
    # Should be scheduled on Monday (2026-06-01)
    assert sessions[0].start_time.strftime("%Y-%m-%d") == "2026-06-01"

if __name__ == "__main__":
    pytest.main([__file__])
