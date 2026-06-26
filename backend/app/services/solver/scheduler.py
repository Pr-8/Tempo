from ortools.sat.python import cp_model
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from uuid import UUID
import math
import itertools

from .models import SolverTask, SolverPreferences, ScheduledSession, Slot, CalendarBlock
from .utils import get_slots, split_task_into_sessions

class TempoScheduler:
    def __init__(self, tasks: List[SolverTask], prefs: SolverPreferences, current_time: datetime, calendar_blocks: List[CalendarBlock] = None):
        self.tasks = tasks
        self.prefs = prefs
        self.current_time = current_time.replace(tzinfo=None) # Work with naive datetimes internally
        self.calendar_blocks = calendar_blocks or []
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

        # Map calendar blocks to slot indices and add as fixed intervals
        overlapping_indices = []
        for block in self.calendar_blocks:
            for s in self.slots:
                # Check overlap: slot start < block end AND slot end > block start
                slot_start = s.dt
                slot_end = s.dt + timedelta(minutes=30)
                if slot_start < block.end_time and slot_end > block.start_time:
                    overlapping_indices.append(s.index)
        
        overlapping_indices = sorted(list(set(overlapping_indices)))
        
        for k, g in itertools.groupby(enumerate(overlapping_indices), lambda ix: ix[0] - ix[1]):
            group = list(map(lambda x: x[1], g))
            if group:
                min_idx = group[0]
                duration_slots = len(group)
                interval = self.model.NewIntervalVar(
                    min_idx, 
                    duration_slots, 
                    min_idx + duration_slots, 
                    f"gcal_block_{min_idx}_{duration_slots}"
                )
                all_intervals.append(interval)

        task_sessions_data = []
        scheduled_score_terms = []
        early_start_penalty_terms = []
        soft_constraint_penalty_terms = []
        
        break_slots = math.ceil(self.prefs.min_break_minutes / 30)

        # Optimization: Pre-calculate slot penalties for weekend/non-preferred hours
        slot_penalties = [0 if s.is_preferred else 50000 for s in self.slots]

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

            if not task.is_fixed:
                deadline_naive = task.deadline.replace(tzinfo=None)
                if deadline_naive < self.current_time:
                    print(f"DEBUG: Skipping task {task.title} - deadline in past")
                    continue

            # Flexible Task
            weight = (6 - task.priority)
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
            
            if last_possible_slot == -1 and not task.is_fixed:
                 print(f"DEBUG: No slots available for task {task.title} before deadline")
                 continue

            last_session_end = None
            for s_idx, duration in enumerate(durations):
                duration_slots = math.ceil(duration / 30)
                is_sess_scheduled = self.model.NewBoolVar(f"is_scheduled_{t_id}_{s_idx}")

                start_var = self.model.NewIntVar(0, num_slots - duration_slots, f"start_{t_id}_{s_idx}")
                end_var = self.model.NewIntVar(duration_slots, num_slots, f"end_{t_id}_{s_idx}")
                interval = self.model.NewOptionalIntervalVar(start_var, duration_slots, end_var, is_sess_scheduled, f"interval_{t_id}_{s_idx}")
                all_intervals.append(interval)
                
                self.model.Add(end_var <= last_possible_slot + 1).OnlyEnforceIf(is_sess_scheduled)
                
                if last_session_end is not None:
                    self.model.Add(start_var >= last_session_end + break_slots).OnlyEnforceIf(is_sess_scheduled)
                
                last_session_end = end_var

                # Penalty for non-preferred slots (Weekend)
                session_penalty = self.model.NewIntVar(0, 50000, f"penalty_{t_id}_{s_idx}")
                self.model.AddElement(start_var, slot_penalties, session_penalty)
                
                # Penalty only applies if scheduled
                actual_penalty = self.model.NewIntVar(0, 50000, f"actual_penalty_{t_id}_{s_idx}")
                self.model.Add(actual_penalty == session_penalty).OnlyEnforceIf(is_sess_scheduled)
                self.model.Add(actual_penalty == 0).OnlyEnforceIf(is_sess_scheduled.Not())
                soft_constraint_penalty_terms.append(actual_penalty)

                # Early start penalty only if scheduled
                actual_start_var = self.model.NewIntVar(0, num_slots, f"actual_start_{t_id}_{s_idx}")
                self.model.Add(actual_start_var == start_var).OnlyEnforceIf(is_sess_scheduled)
                self.model.Add(actual_start_var == 0).OnlyEnforceIf(is_sess_scheduled.Not())

                task_sessions_data.append({
                    "task_id": t_id,
                    "is_scheduled": is_sess_scheduled,
                    "start_var": start_var,
                    "end_var": end_var,
                    "weight": weight,
                    "duration": duration
                })
                scheduled_score_terms.append(is_sess_scheduled * weight)
                early_start_penalty_terms.append(actual_start_var * weight)

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
                        start_time=start_time,
                        end_time=start_time + timedelta(minutes=(e_idx - s_idx) * 30),
                        duration_minutes=(e_idx - s_idx) * 30
                    ))
        return results
