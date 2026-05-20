from ortools.sat.python import cp_model
from datetime import datetime, timedelta, date, time
import math

SLOT_MINUTES = 30

def generate_slots(start_date, horizon_days, available_days_str, day_start_str, day_end_str, blocked_dates=None):
    """
    Generates 30-minute slots over the planning horizon within available windows.
    blocked_dates: List of "YYYY-MM-DD" strings.
    """
    if blocked_dates is None:
        blocked_dates = []
    
    blocked_set = set(blocked_dates)
    
    day_map = {
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6
    }
    allowed_dow = [day_map[d.lower()[:3]] for d in available_days_str]
    
    start_h, start_m = map(int, day_start_str.split(":"))
    end_h, end_m = map(int, day_end_str.split(":"))
    
    slots = []
    current_index = 0
    
    for d in range(horizon_days):
        current_date = start_date + timedelta(days=d)
        if current_date.isoformat() in blocked_set:
            continue
        if current_date.weekday() not in allowed_dow:
            continue
            
        current_dt = datetime.combine(current_date, time(start_h, start_m))
        end_dt = datetime.combine(current_date, time(end_h, end_m))
        
        while current_dt + timedelta(minutes=SLOT_MINUTES) <= end_dt:
            slots.append({
                "index": current_index,
                "dt": current_dt
            })
            current_dt += timedelta(minutes=SLOT_MINUTES)
            current_index += 1
            
    return slots

def solve_schedule(scheduling_request: dict):
    model = cp_model.CpModel()
    
    tasks = scheduling_request.get("tasks", [])
    constraints = scheduling_request.get("constraints", {})
    horizon_days = scheduling_request.get("planning_horizon_days", 21)
    
    windows = constraints.get("available_windows", [])
    blocked_dates = constraints.get("blocked_dates", [])

    if not windows:
        return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}
        
    win = windows[0]
    available_days = win.get("days", ["mon", "tue", "wed", "thu", "fri"])
    day_start = win.get("start", "09:00")
    day_end = win.get("end", "18:00")
    
    # Generate all possible slots
    start_date = date.today()
    slots = generate_slots(start_date, horizon_days, available_days, day_start, day_end, blocked_dates)
    num_slots = len(slots)
    
    if num_slots == 0:
        return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}

    # Helper to find slot index from datetime
    def find_slot_index(dt):
        # Naive search, but efficient enough for slot counts
        for i, s in enumerate(slots):
            if s["dt"] == dt:
                return i
            if s["dt"] > dt:
                return -1
        return -1

    rules = constraints.get("session_rules", {})
    min_session_mins = rules.get("min_session_minutes", 30)
    max_session_mins = rules.get("max_session_minutes", 120)
    pref_session_mins = rules.get("preferred_session_minutes", 60)
    min_break_mins = rules.get("min_break_between_sessions", 30)
    max_sessions_per_day = rules.get("max_sessions_per_day", 3)
    
    break_slots = math.ceil(min_break_mins / SLOT_MINUTES)
    prio_map = {"high": 3, "medium": 2, "low": 1}
    
    all_intervals = []
    task_is_scheduled_vars = {}
    task_sessions_data = []
    scheduled_score_terms = []
    early_start_penalty_terms = []

    for task in tasks:
        t_id = task["id"]
        is_fixed = task.get("is_fixed", False)
        
        if is_fixed:
            # Fixed Task Logic: Punch holes
            f_start = datetime.fromisoformat(task["fixed_start"].replace("Z", ""))
            f_end = datetime.fromisoformat(task["fixed_end"].replace("Z", ""))
            
            start_idx = find_slot_index(f_start)
            # Find end index by duration
            duration_mins = (f_end - f_start).total_seconds() / 60
            duration_slots = int(duration_mins / SLOT_MINUTES)
            
            if start_idx != -1 and start_idx + duration_slots <= num_slots:
                # Create a fixed interval (always scheduled)
                interval = model.NewIntervalVar(start_idx, duration_slots, start_idx + duration_slots, f"fixed_{t_id}")
                all_intervals.append(interval)
                
                # Record it as scheduled
                task_is_scheduled_vars[t_id] = model.NewConstant(1)
                task_sessions_data.append({
                    "task_id": t_id,
                    "is_scheduled": task_is_scheduled_vars[t_id],
                    "start_var": model.NewConstant(start_idx),
                    "end_var": model.NewConstant(start_idx + duration_slots),
                    "weight": 0
                })
            continue

        # Flexible Task Logic (same as before)
        weight = prio_map.get(task.get("priority", "medium").lower(), 2)
        session_mins = max(min_session_mins, min(max_session_mins, pref_session_mins))
        session_slots = session_mins // SLOT_MINUTES
        total_slots_needed = math.ceil(task.get("remaining_hours", 0) * 60 / SLOT_MINUTES)
        num_sessions = math.ceil(total_slots_needed / session_slots)
        
        is_scheduled = model.NewBoolVar(f"is_scheduled_{t_id}")
        task_is_scheduled_vars[t_id] = is_scheduled
        scheduled_score_terms.append(is_scheduled * weight)
        
        deadline_date = date.fromisoformat(task.get("deadline"))
        last_possible_slot = -1
        for i, s in enumerate(slots):
            if s["dt"].date() <= deadline_date:
                last_possible_slot = i
            else:
                break
        
        last_session_end = None
        for s_idx in range(num_sessions):
            duration = session_slots
            start_var = model.NewIntVar(0, num_slots - duration, f"start_{t_id}_{s_idx}")
            end_var = model.NewIntVar(duration, num_slots, f"end_{t_id}_{s_idx}")
            interval = model.NewOptionalIntervalVar(start_var, duration, end_var, is_scheduled, f"interval_{t_id}_{s_idx}")
            all_intervals.append(interval)
            model.Add(end_var <= last_possible_slot + 1).OnlyEnforceIf(is_scheduled)
            if last_session_end is not None:
                model.Add(start_var >= last_session_end + break_slots).OnlyEnforceIf(is_scheduled)
            last_session_end = end_var
            task_sessions_data.append({
                "task_id": t_id,
                "is_scheduled": is_scheduled,
                "start_var": start_var,
                "end_var": end_var,
                "weight": weight
            })
            early_start_penalty_terms.append(start_var * weight)

    model.AddNoOverlap(all_intervals)
    
    # Max sessions per day (skipping fixed tasks in the count to avoid double penalizing)
    days_in_horizon = sorted(list(set(s["dt"].date() for s in slots)))
    for d in days_in_horizon:
        day_slot_indices = [i for i, s in enumerate(slots) if s["dt"].date() == d]
        if not day_slot_indices: continue
        d_start, d_end = min(day_slot_indices), max(day_slot_indices)
        
        sessions_on_this_day = []
        for sess in task_sessions_data:
            if sess["weight"] == 0: continue # Skip fixed tasks
            is_on_day = model.NewBoolVar("")
            b1, b2 = model.NewBoolVar(""), model.NewBoolVar("")
            model.Add(sess["start_var"] >= d_start).OnlyEnforceIf(b1)
            model.Add(sess["start_var"] < d_start).OnlyEnforceIf(b1.Not())
            model.Add(sess["start_var"] <= d_end).OnlyEnforceIf(b2)
            model.Add(sess["start_var"] > d_end).OnlyEnforceIf(b2.Not())
            model.AddBoolAnd([b1, b2, sess["is_scheduled"]]).OnlyEnforceIf(is_on_day)
            model.AddBoolOr([b1.Not(), b2.Not(), sess["is_scheduled"].Not()]).OnlyEnforceIf(is_on_day.Not())
            sessions_on_this_day.append(is_on_day)
        model.Add(sum(sessions_on_this_day) <= max_sessions_per_day)

    model.Maximize(1000000 * sum(scheduled_score_terms) - sum(early_start_penalty_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        scheduled_sessions = []
        for sess in task_sessions_data:
            if solver.Value(sess["is_scheduled"]):
                s_idx, e_idx = solver.Value(sess["start_var"]), solver.Value(sess["end_var"])
                start_dt = slots[s_idx]["dt"]
                end_dt = start_dt + timedelta(minutes=(e_idx - s_idx) * SLOT_MINUTES)
                scheduled_sessions.append({
                    "task_id": sess["task_id"],
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat()
                })
        unschedulable = [t["id"] for t in tasks if not solver.Value(task_is_scheduled_vars[t["id"]])]
        if not scheduled_sessions and tasks:
             return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}
        return {"status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE", "solve_time_ms": 0, "scheduled_sessions": scheduled_sessions, "unschedulable_tasks": unschedulable}
    else:
        return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}
