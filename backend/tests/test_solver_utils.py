from app.services.solver.utils import split_task_into_sessions, get_slots
from datetime import datetime

def test_split_task():
    # 5 hours -> should split into several sessions
    durations = split_task_into_sessions(5.0, 30, 120)
    assert sum(durations) == 300
    assert all(d >= 30 for d in durations)

def test_get_slots():
    slots = get_slots(
        start_date=datetime(2026, 6, 1),
        horizon_days=1,
        available_days=[0, 1, 2, 3, 4, 5, 6],
        start_hour=9,
        end_hour=17,
        blocked_dates=[]
    )
    # 9:00 to 17:00 is 8 hours = 16 slots
    assert len(slots) == 16
