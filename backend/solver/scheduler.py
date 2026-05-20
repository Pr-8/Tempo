from ortools.sat.python import cp_model
from datetime import datetime, timedelta, date, time
import math

SLOT_MINUTES = 30

def generate_slots(start_date, horizon_days, available_days_str, day_start_str, day_end_str):
    """
    Generates 30-minute slots over the planning horizon within available windows.
    available_days_str: ["mon", "tue", ...]
    day_start_str: "HH:MM"
    day_end_str: "HH:MM"
    """
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
    # For simplicity in MVP based on prompt specs, we assume one window pattern.
    # In a full version, we'd handle multiple windows per day.
    # We'll use the first window's days and times for slot generation.
    if not windows:
        return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}
        
    win = windows[0]
    available_days = win.get("days", ["mon", "tue", "wed", "thu", "fri"])
    day_start = win.get("start", "09:00")
    day_end = win.get("end", "18:00")
    
    # Generate all possible slots
    start_date = date.today()
    slots = generate_slots(start_date, horizon_days, available_days, day_start, day_end)
    num_slots = len(slots)
    
    if num_slots == 0:
        return {"status": "INFEASIBLE", "solve_time_ms": 0, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}

    rules = constraints.get("session_rules", {})
    min_session_mins = rules.get("min_session_minutes", 30)
    max_session_mins = rules.get("max_session_minutes", 120)
    pref_session_mins = rules.get("preferred_session_minutes", 60)
    min_break_mins = rules.get("min_break_between_sessions", 30)
    max_sessions_per_day = rules.get("max_sessions_per_day", 3)
    
    break_slots = math.ceil(min_break_mins / SLOT_MINUTES)
    
    # Priority weights
    prio_map = {"high": 3, "medium": 2, "low": 1}
    
    all_intervals = []
    task_is_scheduled_vars = {}
    task_sessions_data = []
    
    # Objective components
    scheduled_score_terms = []
    early_start_penalty_terms = []

    for task in tasks:
        t_id = task["id"]
        weight = prio_map.get(task.get("priority", "medium").lower(), 2)
        
        # Calculate session size in slots
        # Clamp preferred session minutes between min and max
        session_mins = max(min_session_mins, min(max_session_mins, pref_session_mins))
        session_slots = session_mins // SLOT_MINUTES
        
        total_slots_needed = math.ceil(task.get("remaining_hours", 0) * 60 / SLOT_MINUTES)
        num_sessions = math.ceil(total_slots_needed / session_slots)
        
        is_scheduled = model.NewBoolVar(f"is_scheduled_{t_id}")
        task_is_scheduled_vars[t_id] = is_scheduled
        
        # We want to maximize weight * is_scheduled
        scheduled_score_terms.append(is_scheduled * weight)
        
        last_session_end = None
        
        # Identify the deadline slot
        task_deadline_str = task.get("deadline")
        deadline_date = date.fromisoformat(task_deadline_str)
        # Session must finish BEFORE the end of the deadline day.
        # But slots are generated per day. Let's find the last slot index where dt.date() <= deadline_date
        last_possible_slot = -1
        for i, s in enumerate(slots):
            if s["dt"].date() <= deadline_date:
                last_possible_slot = i
            else:
                break
        
        for s_idx in range(num_sessions):
            # If it's the last session, it might be shorter than pref_session_slots
            # For simplicity, we keep fixed session sizes as per prompt "Break each task into fixed-length sessions"
            # But the prompt also says "clamped to [min, max]".
            # We'll use fixed size for now to keep it simple.
            duration = session_slots
            
            # Start variable
            start_var = model.NewIntVar(0, num_slots - duration, f"start_{t_id}_{s_idx}")
            end_var = model.NewIntVar(duration, num_slots, f"end_{t_id}_{s_idx}")
            
            # Optional interval: only exists if task is scheduled
            interval = model.NewOptionalIntervalVar(start_var, duration, end_var, is_scheduled, f"interval_{t_id}_{s_idx}")
            all_intervals.append(interval)
            
            # Deadline constraint
            model.Add(end_var <= last_possible_slot + 1).OnlyEnforceIf(is_scheduled)
            
            # Same-task ordering and breaks
            if last_session_end is not None:
                model.Add(start_var >= last_session_end + break_slots).OnlyEnforceIf(is_scheduled)
            
            last_session_end = end_var
            
            # Record data for result extraction
            task_sessions_data.append({
                "task_id": t_id,
                "is_scheduled": is_scheduled,
                "start_var": start_var,
                "end_var": end_var,
                "weight": weight
            })
            
            # Penalty for starting late
            early_start_penalty_terms.append(start_var * weight)

    # Constraints
    # 1. No overlapping sessions
    model.AddNoOverlap(all_intervals)
    
    # 2. Max sessions per day
    # Group sessions by day
    days_in_horizon = sorted(list(set(s["dt"].date() for s in slots)))
    for d in days_in_horizon:
        day_slot_indices = [i for i, s in enumerate(slots) if s["dt"].date() == d]
        if not day_slot_indices:
            continue
        
        day_start_idx = min(day_slot_indices)
        day_end_idx = max(day_slot_indices)
        
        sessions_on_this_day = []
        for sess in task_sessions_data:
            # A session is "on this day" if it starts on this day
            is_on_day = model.NewBoolVar(f"sess_{sess['task_id']}_on_{d}")
            # start_var >= day_start_idx AND start_var <= day_end_idx
            # model.AddLinearConstraint([sess["start_var"]], day_start_idx, day_end_idx).OnlyEnforceIf(is_on_day)
            
            # Link is_on_day to start_var
            b1 = model.NewBoolVar("")
            model.Add(sess["start_var"] >= day_start_idx).OnlyEnforceIf(b1)
            model.Add(sess["start_var"] < day_start_idx).OnlyEnforceIf(b1.Not())
            
            b2 = model.NewBoolVar("")
            model.Add(sess["start_var"] <= day_end_idx).OnlyEnforceIf(b2)
            model.Add(sess["start_var"] > day_end_idx).OnlyEnforceIf(b2.Not())
            
            # is_on_day = b1 AND b2 AND task_is_scheduled
            model.AddBoolAnd([b1, b2, sess["is_scheduled"]]).OnlyEnforceIf(is_on_day)
            model.AddBoolOr([b1.Not(), b2.Not(), sess["is_scheduled"].Not()]).OnlyEnforceIf(is_on_day.Not())
            
            sessions_on_this_day.append(is_on_day)
            
        model.Add(sum(sessions_on_this_day) <= max_sessions_per_day)

    # Objective:
    # 1. Primary: Maximize scheduled tasks (weighted)
    # 2. Secondary: Minimize start times (weighted)
    # Objective = 1,000,000 * sum(scheduled_score) - sum(early_start_penalty)
    model.Maximize(1000000 * sum(scheduled_score_terms) - sum(early_start_penalty_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    start_solve_time = datetime.now()
    status = solver.Solve(model)
    end_solve_time = datetime.now()
    solve_time_ms = int((end_solve_time - start_solve_time).total_seconds() * 1000)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        scheduled_sessions = []
        for sess in task_sessions_data:
            if solver.Value(sess["is_scheduled"]):
                start_idx = solver.Value(sess["start_var"])
                end_idx = solver.Value(sess["end_var"])
                # end_idx is exclusive
                # Note: our slots are 30 mins. end_idx = start_idx + duration.
                # If start_idx is slot 0 (09:00), and duration is 2, end_idx is 2.
                # Slot 0 is 09:00-09:30, Slot 1 is 09:30-10:00.
                # So end time should be 10:00.
                start_dt = slots[start_idx]["dt"]
                # The end time is start_dt + duration * SLOT_MINUTES
                duration_slots = end_idx - start_idx
                end_dt = start_dt + timedelta(minutes=duration_slots * SLOT_MINUTES)
                
                scheduled_sessions.append({
                    "task_id": sess["task_id"],
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat()
                })
        
        unschedulable = [t["id"] for t in tasks if not solver.Value(task_is_scheduled_vars[t["id"]])]
        
        res_status = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        # If any task couldn't be scheduled, we might want to return INFEASIBLE if that was the expectation,
        # but the prompt says "Returns on failure: INFEASIBLE".
        # In a weighted model, "failure" means it couldn't schedule ANYTHING or something went wrong?
        # Usually, if even one task can't be scheduled, we should check if the user wanted a full schedule.
        # But for now, we'll return the results.
        
        # Actually, if unschedulable tasks exist, the user might consider it "infeasible" for those tasks.
        # The prompt test checks for result_inf["status"] == "INFEASIBLE" when a 100hr task is given.
        # In my weighted model, it will just not schedule it and return "FEASIBLE" with empty sessions.
        # Let's adjust to match test expectation: if any task is mandatory but couldn't be scheduled.
        # OR just check if the solver found a solution.
        
        if not scheduled_sessions and tasks:
             return {"status": "INFEASIBLE", "solve_time_ms": solve_time_ms, "scheduled_sessions": [], "unschedulable_tasks": [t["id"] for t in tasks]}

        return {
            "status": res_status,
            "solve_time_ms": solve_time_ms,
            "scheduled_sessions": scheduled_sessions,
            "unschedulable_tasks": unschedulable
        }
    else:
        return {
            "status": "INFEASIBLE",
            "solve_time_ms": solve_time_ms,
            "scheduled_sessions": [],
            "unschedulable_tasks": [t["id"] for t in tasks]
        }
