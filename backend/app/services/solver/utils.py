from datetime import datetime, timedelta, time
from typing import List
import math
from .models import Slot

def get_slots(start_date: datetime, horizon_days: int, available_days: List[int], start_hour: int, end_hour: int, blocked_dates: List[str]) -> List[Slot]:
    """Generates 30-minute slots over the planning horizon, marking preferred ones."""
    blocked_set = set(blocked_dates)
    slots = []
    current_index = 0
    
    for d in range(horizon_days):
        current_date = (start_date + timedelta(days=d)).date()
        if current_date.isoformat() in blocked_set:
            continue
            
        is_preferred_day = current_date.weekday() in available_days
        
        day_start_dt = datetime.combine(current_date, time(start_hour, 0))
        day_end_dt = datetime.combine(current_date, time(end_hour, 0))
        
        current_dt = day_start_dt
        while current_dt + timedelta(minutes=30) <= day_end_dt:
            if current_dt >= start_date:
                slots.append(Slot(
                    index=current_index,
                    dt=current_dt,
                    is_preferred=is_preferred_day
                ))
                current_index += 1
            current_dt += timedelta(minutes=30)
            
    return slots

def split_task_into_sessions(remaining_hours: float, min_min: int, max_min: int) -> List[int]:
    """Divides task hours into session durations (in minutes)."""
    total_minutes = int(remaining_hours * 60)
    if total_minutes <= 0:
        return []
    
    target = 90
    if target > max_min: target = max_min
    if target < min_min: target = min_min
    
    num_sessions = math.ceil(total_minutes / target)
    if num_sessions == 0: return []
    
    base_duration = total_minutes // num_sessions
    base_duration = (base_duration // 30) * 30
    if base_duration < min_min: base_duration = min_min
    
    durations = []
    remaining = total_minutes
    while remaining > 0:
        d = min(remaining, base_duration if remaining >= base_duration + min_min else remaining)
        if d < min_min and len(durations) > 0:
             durations[-1] += d
             remaining = 0
        else:
            durations.append(d)
            remaining -= d
    return durations
