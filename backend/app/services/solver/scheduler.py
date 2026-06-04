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
