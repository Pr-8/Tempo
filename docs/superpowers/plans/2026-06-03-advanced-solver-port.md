# Advanced Solver Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port advanced solver logic (Fixed Events, Soft Constraints, Weekend Penalties, Partial Scheduling) from legacy code to the modular `app/` structure.

**Architecture:**
- Update `models.py` to include fixed task fields and blocked dates.
- Update `utils.py` to handle sophisticated slot generation including preferred status and blocked dates.
- Re-implement `TempoScheduler` using `NewOptionalIntervalVar` for partial scheduling and adding soft constraints for weekends and session limits.

**Tech Stack:** `ortools`, `pydantic`, `python`.

---

### Task 1: Update Solver DTOs

**Files:**
- Modify: `backend/app/services/solver/models.py`

- [ ] **Step 1: Update `SolverTask` and `SolverPreferences` in `backend/app/services/solver/models.py`**

```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from uuid import UUID

class SolverTask(BaseModel):
    id: UUID
    title: str
    course: str
    remaining_hours: float
    deadline: datetime
    priority: int
    is_fixed: bool = False
    fixed_start: Optional[datetime] = None
    fixed_end: Optional[datetime] = None

class SolverPreferences(BaseModel):
    available_start_hour: int
    available_end_hour: int
    available_days: List[int]
    blocked_dates: List[str] = [] # ISO format dates YYYY-MM-DD
    min_session_minutes: int
    max_session_minutes: int
    max_sessions_per_day: int
    min_break_minutes: int
    planning_horizon_days: int

class Slot(BaseModel):
    index: int
    dt: datetime
    is_preferred: bool

class ScheduledSession(BaseModel):
    task_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
```

- [ ] **Step 2: Commit changes**

### Task 2: Enhance Slot Generation

**Files:**
- Modify: `backend/app/services/solver/utils.py`

- [ ] **Step 1: Update `get_slots` in `backend/app/services/solver/utils.py`**

```python
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
```

- [ ] **Step 2: Commit changes**

### Task 3: Implement Advanced TempoScheduler

**Files:**
- Modify: `backend/app/services/solver/scheduler.py`

- [ ] **Step 1: Replace `TempoScheduler` implementation in `backend/app/services/solver/scheduler.py`**

```python
from ortools.sat.python import cp_model
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from uuid import UUID
import math

from .models import SolverTask, SolverPreferences, ScheduledSession, Slot
from .utils import get_slots, split_task_into_sessions

class TempoScheduler:
    def __init__(self, tasks: List[SolverTask], prefs: SolverPreferences, current_time: datetime):
        self.tasks = tasks
        self.prefs = prefs
        self.current_time = current_time.replace(tzinfo=None) # Work with naive datetimes internally
        self.slots = get_slots(
            self.current_time, 
            self.prefs.planning_horizon_days,
            self.prefs.available_days,
            self.prefs.available_start_hour,
            self.prefs.available_end_hour,
            self.prefs.blocked_dates
        )
        self.model = cp_model.CpModel()
        
    def find_slot_index(self, dt: datetime) -> int:
        for i, s in enumerate(self.slots):
            if s.dt <= dt < s.dt + timedelta(minutes=30):
                return i
            if s.dt > dt:
                return -1
        return -1

    def solve(self) -> List[ScheduledSession]:
        if not self.slots:
            return []

        num_slots = len(self.slots)
        all_intervals = []
        task_sessions_data = []
        scheduled_score_terms = []
        early_start_penalty_terms = []
        soft_constraint_penalty_terms = []
        
        break_slots = math.ceil(self.prefs.min_break_minutes / 30)

        for task in self.tasks:
            t_id = task.id
            if task.is_fixed:
                f_start = task.fixed_start.replace(tzinfo=None)
                f_end = task.fixed_end.replace(tzinfo=None)
                
                start_idx = self.find_slot_index(f_start)
                end_idx = self.find_slot_index(f_end - timedelta(seconds=1))
                
                if start_idx != -1 and end_idx != -1:
                    duration_slots = end_idx - start_idx + 1
                    interval = self.model.NewIntervalVar(start_idx, duration_slots, start_idx + duration_slots, f"fixed_{t_id}")
                    all_intervals.append(interval)
                    
                    task_sessions_data.append({
                        "task_id": t_id,
                        "is_scheduled": self.model.NewConstant(1),
                        "start_var": self.model.NewConstant(start_idx),
                        "end_var": self.model.NewConstant(start_idx + duration_slots),
                        "weight": 0
                    })
                continue

            # Flexible Task
            weight = (6 - task.priority) # Priority 1 (High) -> Weight 5, Priority 5 (Low) -> Weight 1
            durations = split_task_into_sessions(
                task.remaining_hours, 
                self.prefs.min_session_minutes, 
                self.prefs.max_session_minutes
            )
            
            deadline_naive = task.deadline.replace(tzinfo=None)
            last_possible_slot = -1
            for i, s in enumerate(self.slots):
                if s.dt <= deadline_naive:
                    last_possible_slot = i
                else:
                    break
            
            last_session_end = None
            for s_idx, duration in enumerate(durations):
                duration_slots = math.ceil(duration / 30)
                is_sess_scheduled = self.model.NewBoolVar(f"is_scheduled_{t_id}_{s_idx}")

                start_var = self.model.NewIntVar(0, num_slots - duration_slots, f"start_{t_id}_{s_idx}")
                end_var = self.model.NewIntVar(duration_slots, num_slots, f"end_{t_id}_{s_idx}")
                interval = self.model.NewOptionalIntervalVar(start_var, duration_slots, end_var, is_sess_scheduled, f"interval_{t_id}_{s_idx}")
                all_intervals.append(interval)
                
                if last_possible_slot != -1:
                    self.model.Add(end_var <= last_possible_slot + 1).OnlyEnforceIf(is_sess_scheduled)
                
                if last_session_end is not None:
                    self.model.Add(start_var >= last_session_end + break_slots).OnlyEnforceIf(is_sess_scheduled)
                
                last_session_end = end_var

                # Penalty for non-preferred slots (Weekend)
                for i, slot in enumerate(self.slots):
                    if not slot.is_preferred:
                        is_on_bad_slot = self.model.NewBoolVar("")
                        self.model.Add(start_var == i).OnlyEnforceIf(is_on_bad_slot)
                        self.model.Add(start_var != i).OnlyEnforceIf(is_on_bad_slot.Not())
                        soft_constraint_penalty_terms.append(is_on_bad_slot * 50000)

                task_sessions_data.append({
                    "task_id": t_id,
                    "is_scheduled": is_sess_scheduled,
                    "start_var": start_var,
                    "end_var": end_var,
                    "weight": weight,
                    "duration": duration
                })
                scheduled_score_terms.append(is_sess_scheduled * weight)
                early_start_penalty_terms.append(start_var * weight)

        self.model.AddNoOverlap(all_intervals)
        
        # Max sessions per day
        days_in_horizon = sorted(list(set(s.dt.date() for s in self.slots)))
        for d in days_in_horizon:
            day_slot_indices = [i for i, s in enumerate(self.slots) if s.dt.date() == d]
            if not day_slot_indices: continue
            d_start, d_end = min(day_slot_indices), max(day_slot_indices)
            
            sessions_on_this_day = []
            for sess in task_sessions_data:
                if sess["weight"] == 0: continue # Skip fixed
                is_on_day = self.model.NewBoolVar("")
                b1, b2 = self.model.NewBoolVar(""), self.model.NewBoolVar("")
                self.model.Add(sess["start_var"] >= d_start).OnlyEnforceIf(b1)
                self.model.Add(sess["start_var"] < d_start).OnlyEnforceIf(b1.Not())
                self.model.Add(sess["start_var"] <= d_end).OnlyEnforceIf(b2)
                self.model.Add(sess["start_var"] > d_end).OnlyEnforceIf(b2.Not())
                self.model.AddBoolAnd([b1, b2, sess["is_scheduled"]]).OnlyEnforceIf(is_on_day)
                self.model.AddBoolOr([b1.Not(), b2.Not(), sess["is_scheduled"].Not()]).OnlyEnforceIf(is_on_day.Not())
                sessions_on_this_day.append(is_on_day)
            
            total_sessions_today = sum(sessions_on_this_day)
            excess_sessions = self.model.NewIntVar(0, len(self.tasks) * 2, "")
            self.model.Add(excess_sessions >= total_sessions_today - self.prefs.max_sessions_per_day)
            soft_constraint_penalty_terms.append(excess_sessions * 20000)

        self.model.Maximize(1000000 * sum(scheduled_score_terms) 
                       - sum(early_start_penalty_terms) 
                       - sum(soft_constraint_penalty_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status = solver.Solve(self.model)
        
        results = []
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for sess in task_sessions_data:
                if solver.Value(sess["is_scheduled"]):
                    s_idx = solver.Value(sess["start_var"])
                    e_idx = solver.Value(sess["end_var"])
                    start_time = self.slots[s_idx].dt
                    results.append(ScheduledSession(
                        task_id=sess["task_id"],
                        start_time=start_time.replace(tzinfo=timezone.utc),
                        end_time=(start_time + timedelta(minutes=(e_idx - s_idx) * 30)).replace(tzinfo=timezone.utc),
                        duration_minutes=(e_idx - s_idx) * 30
                    ))
        return results
```

- [ ] **Step 2: Commit changes**

### Task 4: Validation

- [ ] **Step 1: Write a test script `backend/tests/test_advanced_solver_port.py`**
- [ ] **Step 2: Run the test and verify it passes**
