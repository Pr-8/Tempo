# Tempo — Implementation Guide
## Phases 1 & 2: MVP + Chat Interface

---

## Prerequisites & Environment Setup

### Required installs

**Backend**
```bash
# Python 3.11+
pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary
pip install google-generativeai          # Gemini AI Studio SDK
pip install ortools                      # OR-Tools constraint solver
pip install redis rq                     # Job queue
pip install python-dotenv pydantic
pip install rapidfuzz                    # Fuzzy deduplication (Phase 2+)
```

**Frontend**
```bash
npm create vite@latest tempo-web -- --template react
cd tempo-web
npm install axios react-query zustand
npm install @fullcalendar/react @fullcalendar/daygrid @fullcalendar/timegrid
npm install react-hook-form date-fns
```

**Infrastructure**
- PostgreSQL 15+
- Redis (for job queue)
- A free Google AI Studio account → get API key at https://aistudio.google.com

### Environment variables

```
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/tempo
GEMINI_API_KEY=your_key_here
REDIS_URL=redis://localhost:6379
PLANNING_HORIZON_DAYS=21
```

---

## Phase 1 — MVP

### Goal
Manual task entry → solver generates schedule → user marks sessions complete or failed → auto-reschedule. Validate the core loop works and feels useful.

---

### Step 1: Database Schema

Create your models first. Everything else depends on this.

**`models.py`**
```python
from sqlalchemy import Column, String, Float, Date, DateTime, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid, enum

Base = declarative_base()

class TaskStatus(str, enum.Enum):
    pending    = "pending"
    complete   = "complete"
    failed     = "failed"

class SessionStatus(str, enum.Enum):
    pending  = "pending"
    complete = "complete"
    failed   = "failed"

class Task(Base):
    __tablename__ = "tasks"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title           = Column(String, nullable=False)
    course          = Column(String, nullable=True)
    estimated_hours = Column(Float, nullable=False)
    deadline        = Column(Date, nullable=False)
    priority        = Column(Enum("low","medium","high", name="priority_enum"), default="medium")
    status          = Column(Enum(TaskStatus), default=TaskStatus.pending)
    source          = Column(String, default="manual")
    created_at      = Column(DateTime)

class ScheduledSession(Base):
    __tablename__ = "scheduled_sessions"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id    = Column(UUID(as_uuid=True), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time   = Column(DateTime, nullable=False)
    status     = Column(Enum(SessionStatus), default=SessionStatus.pending)
    failed_at  = Column(DateTime, nullable=True)

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    available_days           = Column(String)   # stored as comma-separated: "mon,tue,wed,thu,fri"
    day_start                = Column(String, default="09:00")
    day_end                  = Column(String, default="18:00")
    max_sessions_per_day     = Column(Integer, default=3)
    min_break_minutes        = Column(Integer, default=30)
    preferred_session_mins   = Column(Integer, default=60)
    max_session_mins         = Column(Integer, default=120)
    schedule_dirty           = Column(Boolean, default=False)
```

Run migrations:
```bash
alembic init alembic
# configure alembic.ini with DATABASE_URL
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

### Step 2: The Constraint Solver

This is the most important component. Build and test it in isolation before touching anything else.

**`solver/scheduler.py`**
```python
from ortools.sat.python import cp_model
from datetime import datetime, timedelta, date
from typing import List, Dict

SLOT_MINUTES = 30  # time is discretised into 30-min slots

def generate_slots(
    start_date: date,
    horizon_days: int,
    available_days: List[str],
    day_start: str,
    day_end: str
) -> List[Dict]:
    """
    Generate all valid 30-minute slots across the planning horizon.
    Returns list of {slot_index, datetime} dicts.
    """
    day_map = {"mon":0,"tue":1,"wed":2,"thu":3,"fri":4,"sat":5,"sun":6}
    available_day_ints = [day_map[d] for d in available_days]
    
    start_h, start_m = map(int, day_start.split(":"))
    end_h, end_m     = map(int, day_end.split(":"))
    
    slots = []
    idx   = 0
    for day_offset in range(horizon_days):
        current_date = start_date + timedelta(days=day_offset)
        if current_date.weekday() not in available_day_ints:
            continue
        slot_time = datetime(
            current_date.year, current_date.month, current_date.day,
            start_h, start_m
        )
        end_time = datetime(
            current_date.year, current_date.month, current_date.day,
            end_h, end_m
        )
        while slot_time < end_time:
            slots.append({"index": idx, "dt": slot_time})
            slot_time += timedelta(minutes=SLOT_MINUTES)
            idx += 1
    return slots


def solve_schedule(scheduling_request: Dict) -> Dict:
    """
    Takes a SchedulingRequest dict and returns a SolverOutput dict.
    
    SchedulingRequest shape:
    {
        tasks: [{id, title, remaining_hours, deadline, priority}],
        constraints: {
            available_windows: [{days, start, end}],
            blocked_dates: ["2026-05-15"],
            session_rules: {min_session_minutes, max_session_minutes,
                            min_break_between_sessions, max_sessions_per_day}
        },
        planning_horizon_days: 21
    }
    """
    model   = cp_model.CpModel()
    tasks   = scheduling_request["tasks"]
    rules   = scheduling_request["constraints"]["session_rules"]
    horizon = scheduling_request.get("planning_horizon_days", 21)
    today   = date.today()
    
    avail        = scheduling_request["constraints"]["available_windows"][0]
    blocked_dates = set(scheduling_request["constraints"].get("blocked_dates", []))
    
    all_slots = generate_slots(
        today, horizon, avail["days"], avail["start"], avail["end"]
    )
    
    # Filter out blocked dates
    all_slots = [
        s for s in all_slots
        if s["dt"].date().isoformat() not in blocked_dates
    ]
    
    min_slots  = rules["min_session_minutes"]  // SLOT_MINUTES
    max_slots  = rules["max_session_minutes"]  // SLOT_MINUTES
    break_slots = rules["min_break_between_sessions"] // SLOT_MINUTES
    
    # --- Build task chunks ---
    # Each task is broken into sessions. We decide session count based on
    # total hours and max session length. Each session is a variable-length
    # block of contiguous slots.
    
    # For simplicity in v1: fix session length to preferred_session_mins
    # and compute how many sessions per task.
    pref_slots = rules.get("preferred_session_minutes", 60) // SLOT_MINUTES
    pref_slots = max(min_slots, min(pref_slots, max_slots))
    
    task_sessions = []  # list of {task_id, session_idx, num_slots, deadline_slot}
    for task in tasks:
        total_slots   = int((task["remaining_hours"] * 60) / SLOT_MINUTES)
        deadline_dt   = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
        deadline_slot = next(
            (s["index"] for s in reversed(all_slots)
             if s["dt"].date() <= deadline_dt),
            len(all_slots) - 1
        )
        sessions_needed = max(1, round(total_slots / pref_slots))
        slots_per_session = total_slots // sessions_needed
        slots_per_session = max(min_slots, min(slots_per_session, max_slots))
        
        for i in range(sessions_needed):
            task_sessions.append({
                "task_id":       str(task["id"]),
                "session_idx":   i,
                "num_slots":     slots_per_session,
                "deadline_slot": deadline_slot,
                "priority":      task["priority"]
            })
    
    n_slots   = len(all_slots)
    slot_map  = {s["index"]: s["dt"] for s in all_slots}
    
    # --- Decision variables ---
    # start_var[session_key] = index of first slot assigned to this session
    start_vars = {}
    for ts in task_sessions:
        key = (ts["task_id"], ts["session_idx"])
        start_vars[key] = model.NewIntVar(
            0,
            max(0, ts["deadline_slot"] - ts["num_slots"]),
            f"start_{ts['task_id']}_{ts['session_idx']}"
        )
    
    # --- Hard constraints ---
    
    # 1. No overlap between any two sessions
    # Use interval vars for efficient no-overlap constraint
    interval_vars = {}
    for ts in task_sessions:
        key = (ts["task_id"], ts["session_idx"])
        interval_vars[key] = model.NewIntervalVar(
            start_vars[key],
            ts["num_slots"],
            start_vars[key] + ts["num_slots"],
            f"interval_{ts['task_id']}_{ts['session_idx']}"
        )
    model.AddNoOverlap(list(interval_vars.values()))
    
    # 2. All sessions for a task must finish before deadline
    for ts in task_sessions:
        key = (ts["task_id"], ts["session_idx"])
        model.Add(
            start_vars[key] + ts["num_slots"] <= ts["deadline_slot"] + 1
        )
    
    # 3. Sessions of the same task must be ordered
    task_session_groups = {}
    for ts in task_sessions:
        task_session_groups.setdefault(ts["task_id"], []).append(ts)
    
    for task_id, sessions in task_session_groups.items():
        for i in range(len(sessions) - 1):
            k1 = (task_id, sessions[i]["session_idx"])
            k2 = (task_id, sessions[i+1]["session_idx"])
            model.Add(
                start_vars[k2] >= start_vars[k1] + sessions[i]["num_slots"] + break_slots
            )
    
    # 4. Max sessions per day
    max_per_day = rules["max_sessions_per_day"]
    slots_per_day = {}
    for s in all_slots:
        day_key = s["dt"].date()
        slots_per_day.setdefault(day_key, [])
        slots_per_day[day_key].append(s["index"])
    
    for day, day_slot_indices in slots_per_day.items():
        if not day_slot_indices:
            continue
        day_min = min(day_slot_indices)
        day_max = max(day_slot_indices)
        sessions_this_day = []
        for ts in task_sessions:
            key = (ts["task_id"], ts["session_idx"])
            is_on_day = model.NewBoolVar(f"on_day_{day}_{key}")
            model.Add(start_vars[key] >= day_min).OnlyEnforceIf(is_on_day)
            model.Add(start_vars[key] <= day_max).OnlyEnforceIf(is_on_day)
            model.Add(start_vars[key] < day_min).OnlyEnforceIf(is_on_day.Not())
            sessions_this_day.append(is_on_day)
        if sessions_this_day:
            model.Add(sum(sessions_this_day) <= max_per_day)
    
    # --- Objective: minimise deadline risk ---
    # Penalise scheduling sessions close to their deadline.
    priority_weight = {"high": 3, "medium": 2, "low": 1}
    objective_terms = []
    for ts in task_sessions:
        key = (ts["task_id"], ts["session_idx"])
        weight = priority_weight.get(ts["priority"], 1)
        # Penalise later scheduling weighted by priority
        objective_terms.append(weight * start_vars[key])
    model.Minimize(sum(objective_terms))
    
    # --- Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    
    status_name = solver.StatusName(status)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        scheduled = []
        for ts in task_sessions:
            key        = (ts["task_id"], ts["session_idx"])
            slot_idx   = solver.Value(start_vars[key])
            start_dt   = slot_map.get(slot_idx)
            if start_dt is None:
                continue
            end_dt = start_dt + timedelta(minutes=ts["num_slots"] * SLOT_MINUTES)
            scheduled.append({
                "task_id":    ts["task_id"],
                "start":      start_dt.isoformat(),
                "end":        end_dt.isoformat()
            })
        return {
            "status":                "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "solve_time_ms":         round(solver.WallTime() * 1000),
            "scheduled_sessions":    scheduled,
            "unschedulable_tasks":   []
        }
    else:
        # Infeasible — identify which tasks couldn't be placed
        # (simplified: report all tasks as unschedulable)
        return {
            "status":              "INFEASIBLE",
            "solve_time_ms":       round(solver.WallTime() * 1000),
            "scheduled_sessions":  [],
            "unschedulable_tasks": [t["id"] for t in tasks]
        }
```

**Test the solver in isolation before proceeding:**
```python
# test_solver.py
from solver.scheduler import solve_schedule
from datetime import date, timedelta

result = solve_schedule({
    "planning_horizon_days": 14,
    "tasks": [
        {
            "id": "t1",
            "title": "Calculus Revision",
            "remaining_hours": 3.0,
            "deadline": (date.today() + timedelta(days=7)).isoformat(),
            "priority": "high"
        },
        {
            "id": "t2",
            "title": "Physics Problem Set",
            "remaining_hours": 2.0,
            "deadline": (date.today() + timedelta(days=10)).isoformat(),
            "priority": "medium"
        }
    ],
    "constraints": {
        "available_windows": [
            {"days": ["mon","tue","wed","thu","fri"], "start": "09:00", "end": "18:00"}
        ],
        "blocked_dates": [],
        "session_rules": {
            "min_session_minutes": 45,
            "max_session_minutes": 120,
            "preferred_session_minutes": 60,
            "min_break_between_sessions": 30,
            "max_sessions_per_day": 3
        }
    }
})

print(result["status"])
for s in result["scheduled_sessions"]:
    print(f"  Task {s['task_id']}: {s['start']} → {s['end']}")
```

This must work cleanly before you build anything else.

---

### Step 3: Context Builder + Scheduling Request Assembler

This function is called before every solver run. It reads from the DB and produces the Scheduling Request JSON the solver expects.

**`scheduling/context_builder.py`**
```python
from datetime import date
from db import get_db
from models import Task, TaskStatus, UserPreferences

def build_scheduling_request(user_id: str) -> dict:
    db    = get_db()
    prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
    tasks = db.query(Task).filter(
        Task.status == TaskStatus.pending
    ).all()
    
    # Compute remaining hours per task
    # (estimated_hours minus sum of completed session durations)
    task_list = []
    for t in tasks:
        completed_mins = sum_completed_session_minutes(t.id, db)
        remaining_hrs  = max(0, t.estimated_hours - (completed_mins / 60))
        if remaining_hrs <= 0:
            continue
        task_list.append({
            "id":              str(t.id),
            "title":           t.title,
            "remaining_hours": remaining_hrs,
            "deadline":        t.deadline.isoformat(),
            "priority":        t.priority
        })
    
    return {
        "planning_horizon_days": 21,
        "tasks": task_list,
        "constraints": {
            "available_windows": [{
                "days":  prefs.available_days.split(","),
                "start": prefs.day_start,
                "end":   prefs.day_end
            }],
            "blocked_dates": [],
            "session_rules": {
                "min_session_minutes":         45,
                "max_session_minutes":         prefs.max_session_mins,
                "preferred_session_minutes":   prefs.preferred_session_mins,
                "min_break_between_sessions":  prefs.min_break_minutes,
                "max_sessions_per_day":        prefs.max_sessions_per_day
            }
        }
    }
```

---

### Step 4: Gemini Explainer Call

**`llm/explainer.py`**
```python
import google.generativeai as genai
import os, json

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

EXPLAINER_PROMPT = """
You are a practical study coach. A scheduling algorithm has produced 
the study plan below for a student. Write 3-4 sentences explaining:
1. What was prioritised first and why
2. Any heavy days or potential pressure points to be aware of
3. Any tasks that could NOT be scheduled (if the list is non-empty, 
   say exactly which ones and why)

Be direct and specific. Use plain English. No bullet points. 
Address the student as "you". Do not repeat the schedule back 
to them — they can see it. Only flag things worth knowing.
"""

def generate_schedule_explanation(
    solver_output: dict,
    tasks: list
) -> str:
    task_lookup = {str(t["id"]): t for t in tasks}
    
    # Summarise what got scheduled
    scheduled_summary = []
    for s in solver_output["scheduled_sessions"]:
        task = task_lookup.get(s["task_id"], {})
        scheduled_summary.append(
            f"- {task.get('title','?')}: {s['start'][:16]} to {s['end'][11:16]}"
        )
    
    unschedulable = []
    for tid in solver_output.get("unschedulable_tasks", []):
        task = task_lookup.get(str(tid), {})
        unschedulable.append(task.get("title", str(tid)))
    
    user_message = f"""
SCHEDULED SESSIONS:
{chr(10).join(scheduled_summary)}

TASKS THAT COULD NOT BE SCHEDULED:
{', '.join(unschedulable) if unschedulable else 'None — all tasks fit.'}

TASK DETAILS (for context):
{json.dumps([{
    'title': t.get('title'),
    'deadline': t.get('deadline'),
    'priority': t.get('priority'),
    'remaining_hours': t.get('remaining_hours')
} for t in tasks], indent=2)}
"""
    
    response = model.generate_content([
        {"role": "user", "parts": [EXPLAINER_PROMPT + "\n\n" + user_message]}
    ])
    return response.text.strip()
```

---

### Step 5: Background Job (Reschedule Pipeline)

The full pipeline runs as a background job. It is triggered by a dirty flag.

**`jobs/reschedule.py`**
```python
from scheduling.context_builder import build_scheduling_request
from solver.scheduler import solve_schedule
from llm.explainer import generate_schedule_explanation
from db import get_db
from models import ScheduledSession, SessionStatus
from datetime import datetime

def run_reschedule_pipeline(user_id: str):
    db = get_db()
    
    # 1. Build scheduling request from DB state
    scheduling_request = build_scheduling_request(user_id)
    
    if not scheduling_request["tasks"]:
        return  # nothing to schedule
    
    # 2. Run solver
    solver_output = solve_schedule(scheduling_request)
    
    # 3. Clear all pending (not yet started) sessions
    db.query(ScheduledSession).filter(
        ScheduledSession.status == SessionStatus.pending
    ).delete()
    db.commit()
    
    # 4. Write new sessions
    for s in solver_output["scheduled_sessions"]:
        session = ScheduledSession(
            task_id    = s["task_id"],
            start_time = datetime.fromisoformat(s["start"]),
            end_time   = datetime.fromisoformat(s["end"]),
            status     = SessionStatus.pending
        )
        db.add(session)
    db.commit()
    
    # 5. Generate LLM explanation
    explanation = generate_schedule_explanation(
        solver_output,
        scheduling_request["tasks"]
    )
    
    # Store explanation against user record
    # (simple: store as a string field on UserPreferences for MVP)
    prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
    prefs.last_schedule_explanation = explanation
    prefs.schedule_dirty = False
    db.commit()
    
    return solver_output
```

**Enqueue jobs with RQ:**
```python
# anywhere a dirty flag should be set:
from redis import Redis
from rq import Queue

q = Queue(connection=Redis.from_url(os.environ["REDIS_URL"]))

def mark_schedule_dirty(user_id: str):
    q.enqueue(run_reschedule_pipeline, user_id)
```

---

### Step 6: FastAPI Routes

**`routes/tasks.py`**
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from uuid import UUID

router = APIRouter(prefix="/tasks")

class TaskCreate(BaseModel):
    title:           str
    course:          str | None = None
    estimated_hours: float
    deadline:        date
    priority:        str = "medium"

@router.post("/")
def create_task(body: TaskCreate):
    # validate
    if body.estimated_hours <= 0 or body.estimated_hours > 40:
        raise HTTPException(400, "estimated_hours must be between 0 and 40")
    if body.deadline <= date.today():
        raise HTTPException(400, "deadline must be in the future")
    
    task = Task(
        title           = body.title,
        course          = body.course,
        estimated_hours = body.estimated_hours,
        deadline        = body.deadline,
        priority        = body.priority,
        status          = TaskStatus.pending,
        source          = "manual",
        created_at      = datetime.utcnow()
    )
    db.add(task)
    db.commit()
    mark_schedule_dirty(HARDCODED_USER_ID)  # single user in MVP
    return task

@router.get("/")
def list_tasks():
    return db.query(Task).order_by(Task.deadline).all()

@router.delete("/{task_id}")
def delete_task(task_id: UUID):
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task)
    db.commit()
    mark_schedule_dirty(HARDCODED_USER_ID)
    return {"ok": True}
```

**`routes/sessions.py`**
```python
router = APIRouter(prefix="/sessions")

@router.patch("/{session_id}/complete")
def mark_complete(session_id: UUID):
    session = db.query(ScheduledSession).get(session_id)
    if not session:
        raise HTTPException(404)
    session.status = SessionStatus.complete
    db.commit()
    # Check if all sessions for this task are complete
    remaining = db.query(ScheduledSession).filter(
        ScheduledSession.task_id == session.task_id,
        ScheduledSession.status  == SessionStatus.pending
    ).count()
    if remaining == 0:
        task = db.query(Task).get(session.task_id)
        task.status = TaskStatus.complete
        db.commit()
    return {"ok": True}

@router.patch("/{session_id}/failed")
def mark_failed(session_id: UUID):
    session = db.query(ScheduledSession).get(session_id)
    if not session:
        raise HTTPException(404)
    session.status   = SessionStatus.failed
    session.failed_at = datetime.utcnow()
    db.commit()
    # Trigger reschedule
    mark_schedule_dirty(HARDCODED_USER_ID)
    return {"ok": True, "message": "Rescheduling..."}

@router.get("/")
def get_schedule():
    sessions = db.query(ScheduledSession).filter(
        ScheduledSession.status == SessionStatus.pending
    ).order_by(ScheduledSession.start_time).all()
    return sessions
```

**`routes/preferences.py`**
```python
router = APIRouter(prefix="/preferences")

class PrefsUpdate(BaseModel):
    available_days:         list[str]
    day_start:              str
    day_end:                str
    max_sessions_per_day:   int = 3
    min_break_minutes:      int = 30
    preferred_session_mins: int = 60
    max_session_mins:       int = 120

@router.put("/")
def update_preferences(body: PrefsUpdate):
    prefs = db.query(UserPreferences).filter_by(
        user_id=HARDCODED_USER_ID
    ).first()
    prefs.available_days         = ",".join(body.available_days)
    prefs.day_start              = body.day_start
    prefs.day_end                = body.day_end
    prefs.max_sessions_per_day   = body.max_sessions_per_day
    prefs.min_break_minutes      = body.min_break_minutes
    prefs.preferred_session_mins = body.preferred_session_mins
    prefs.max_session_mins       = body.max_session_mins
    db.commit()
    mark_schedule_dirty(HARDCODED_USER_ID)
    return {"ok": True}
```

---

### Step 7: Frontend — Schedule View

Use FullCalendar for the week view. Keep the frontend thin — it fetches data, displays it, and fires API calls on user actions.

**`components/ScheduleView.jsx`**
```jsx
import FullCalendar from '@fullcalendar/react'
import timeGridPlugin from '@fullcalendar/timegrid'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import axios from 'axios'

export default function ScheduleView() {
  const qc = useQueryClient()

  const { data: sessions } = useQuery('sessions', () =>
    axios.get('/api/sessions').then(r => r.data)
  )

  const { data: tasks } = useQuery('tasks', () =>
    axios.get('/api/tasks').then(r => r.data)
  )

  const { data: prefs } = useQuery('prefs', () =>
    axios.get('/api/preferences').then(r => r.data)
  )

  const completeMutation = useMutation(
    (id) => axios.patch(`/api/sessions/${id}/complete`),
    { onSuccess: () => qc.invalidateQueries(['sessions','tasks']) }
  )

  const failMutation = useMutation(
    (id) => axios.patch(`/api/sessions/${id}/failed`),
    { onSuccess: () => {
      qc.invalidateQueries(['sessions','tasks'])
      // Poll for updated schedule after reschedule job completes
      setTimeout(() => qc.invalidateQueries('sessions'), 3000)
    }}
  )

  // Map sessions to FullCalendar event format
  const taskMap = Object.fromEntries((tasks||[]).map(t => [t.id, t]))
  const events = (sessions||[]).map(s => ({
    id:    s.id,
    title: taskMap[s.task_id]?.title || 'Session',
    start: s.start_time,
    end:   s.end_time,
    extendedProps: { session: s, task: taskMap[s.task_id] }
  }))

  return (
    <div className="schedule-container">
      {prefs?.last_schedule_explanation && (
        <div className="llm-summary">
          <p>{prefs.last_schedule_explanation}</p>
        </div>
      )}

      <FullCalendar
        plugins={[timeGridPlugin]}
        initialView="timeGridWeek"
        events={events}
        eventContent={(arg) => (
          <SessionCard
            session={arg.event.extendedProps.session}
            task={arg.event.extendedProps.task}
            onComplete={() => completeMutation.mutate(arg.event.id)}
            onFail={() => failMutation.mutate(arg.event.id)}
          />
        )}
        headerToolbar={{
          left:  'prev,next today',
          center:'title',
          right: ''
        }}
        slotMinTime="07:00:00"
        slotMaxTime="22:00:00"
        allDaySlot={false}
      />
    </div>
  )
}

function SessionCard({ session, task, onComplete, onFail }) {
  const priorityColor = { high:'#ef4444', medium:'#f59e0b', low:'#10b981' }
  return (
    <div style={{ padding: '4px', fontSize: '12px' }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        backgroundColor: priorityColor[task?.priority],
        display: 'inline-block', marginRight: 4
      }}/>
      <strong>{task?.title}</strong>
      {task?.course && <div style={{opacity:0.7}}>{task.course}</div>}
      <div style={{ marginTop: 4, display: 'flex', gap: 4 }}>
        <button onClick={onComplete} style={{fontSize:10}}>✓ Done</button>
        <button onClick={onFail}    style={{fontSize:10}}>✗ Failed</button>
      </div>
    </div>
  )
}
```

---

### Phase 1 Completion Checklist

```
[ ] Database schema created and migrated
[ ] Solver tested in isolation with hardcoded input
[ ] Context builder assembles valid SchedulingRequest from DB
[ ] Reschedule pipeline runs end-to-end (solver + explainer + DB write)
[ ] Background job queue running (Redis + RQ worker)
[ ] POST /tasks creates task and triggers reschedule
[ ] PATCH /sessions/:id/complete marks session done
[ ] PATCH /sessions/:id/failed marks session failed and triggers reschedule
[ ] Schedule view renders sessions in FullCalendar
[ ] LLM explanation appears at top of schedule view
[ ] Onboarding form saves preferences and triggers first schedule run
```

---
---

## Phase 2 — Chat Interface

### Goal
Let users manage their schedule through natural conversation. Adding tasks, moving sessions, blocking time, and asking questions should all be possible via chat without touching the manual form. Introduce conversational memory so the system remembers things users tell it.

**Build Phase 2 only after Phase 1 is stable and tested.**

---

### New Components in Phase 2

1. Chat UI (frontend)
2. Tool definitions (what actions the LLM can trigger)
3. Tool executor (backend functions that carry out tool calls)
4. Chat route (orchestrates the LLM ↔ tool loop)
5. Memory extraction (background job that persists facts from chat)
6. Context builder update (injects memories into every LLM call)

---

### Step 1: Extend the Database

```python
# Add to models.py

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role       = Column(String)     # "user" | "assistant" | "tool"
    content    = Column(String)
    tool_calls = Column(JSON, nullable=True)   # log of tool calls made
    created_at = Column(DateTime)

class UserMemory(Base):
    __tablename__ = "user_memories"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content           = Column(String)    # "User has football every Thursday at 7pm"
    memory_type       = Column(String)    # "constraint" | "preference" | "context"
    created_at        = Column(DateTime)
    last_referenced_at = Column(DateTime)
```

Run migration:
```bash
alembic revision --autogenerate -m "add chat and memory tables"
alembic upgrade head
```

---

### Step 2: Define Tools

Tools are the actions the LLM can trigger. Define them as a list of schemas passed to Gemini on every chat call.

**`llm/tools.py`**
```python
TOOLS = [
    {
        "name": "add_task",
        "description": (
            "Add a new study task to the user's schedule. "
            "Use this when the user mentions a new assignment, exam, or deadline."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title":           {"type": "string"},
                "course":          {"type": "string", "nullable": True},
                "estimated_hours": {"type": "number"},
                "deadline":        {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "priority":        {"type": "string", "enum": ["low","medium","high"]}
            },
            "required": ["title", "estimated_hours", "deadline", "priority"]
        }
    },
    {
        "name": "move_session",
        "description": "Move a scheduled session to a different time.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id":     {"type": "string"},
                "new_start_time": {"type": "string", "description": "ISO datetime"}
            },
            "required": ["session_id", "new_start_time"]
        }
    },
    {
        "name": "block_time",
        "description": (
            "Block out a date or time range so nothing gets scheduled there. "
            "Use when the user says they are unavailable at a certain time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "reason": {"type": "string", "nullable": True}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Retrieve the current schedule for a date range so you can answer questions about it.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"}
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "update_preference",
        "description": "Update a user preference such as working hours or max sessions per day.",
        "parameters": {
            "type": "object",
            "properties": {
                "key":   {"type": "string",
                          "description": "One of: day_start, day_end, max_sessions_per_day, min_break_minutes"},
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "ask_clarification",
        "description": (
            "Ask the user a specific clarifying question when required fields "
            "are missing or ambiguous. Only ask ONE question at a time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"}
            },
            "required": ["question"]
        }
    }
]
```

---

### Step 3: Tool Executor

When Gemini returns a tool call, this module executes it and returns the result.

**`llm/tool_executor.py`**
```python
import json
from datetime import datetime, date
from models import Task, TaskStatus, ScheduledSession, SessionStatus, UserPreferences
from jobs.reschedule import mark_schedule_dirty
from db import get_db

HARDCODED_USER_ID = "user_1"

def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool call and return a string result."""
    db = get_db()
    
    if tool_name == "add_task":
        task = Task(
            title           = tool_args["title"],
            course          = tool_args.get("course"),
            estimated_hours = tool_args["estimated_hours"],
            deadline        = date.fromisoformat(tool_args["deadline"]),
            priority        = tool_args["priority"],
            status          = TaskStatus.pending,
            source          = "chat",
            created_at      = datetime.utcnow()
        )
        db.add(task)
        db.commit()
        mark_schedule_dirty(HARDCODED_USER_ID)
        return f"Task '{task.title}' added. Schedule is being updated."

    elif tool_name == "block_time":
        # Store as a blocked date in preferences
        # (MVP: simple comma-separated list on prefs table)
        prefs = db.query(UserPreferences).filter_by(
            user_id=HARDCODED_USER_ID
        ).first()
        blocked = prefs.blocked_dates or ""
        blocked_list = [d for d in blocked.split(",") if d]
        if tool_args["date"] not in blocked_list:
            blocked_list.append(tool_args["date"])
            prefs.blocked_dates = ",".join(blocked_list)
            db.commit()
        mark_schedule_dirty(HARDCODED_USER_ID)
        return f"Blocked {tool_args['date']}. Schedule is being updated."

    elif tool_name == "get_schedule":
        start = datetime.fromisoformat(tool_args["start_date"])
        end   = datetime.fromisoformat(tool_args["end_date"])
        sessions = db.query(ScheduledSession).filter(
            ScheduledSession.start_time >= start,
            ScheduledSession.start_time <= end,
            ScheduledSession.status == SessionStatus.pending
        ).order_by(ScheduledSession.start_time).all()
        
        if not sessions:
            return "No sessions scheduled in that range."
        
        lines = []
        for s in sessions:
            task = db.query(Task).get(s.task_id)
            lines.append(
                f"- {task.title}: {s.start_time.strftime('%a %b %d, %H:%M')} "
                f"to {s.end_time.strftime('%H:%M')}"
            )
        return "\n".join(lines)

    elif tool_name == "update_preference":
        prefs = db.query(UserPreferences).filter_by(
            user_id=HARDCODED_USER_ID
        ).first()
        setattr(prefs, tool_args["key"], tool_args["value"])
        db.commit()
        mark_schedule_dirty(HARDCODED_USER_ID)
        return f"Updated {tool_args['key']} to {tool_args['value']}."

    elif tool_name == "ask_clarification":
        # Special case — not a DB action, just return the question
        # The chat route handles this by returning the question to the user
        return f"CLARIFICATION:{tool_args['question']}"

    elif tool_name == "move_session":
        session = db.query(ScheduledSession).get(tool_args["session_id"])
        if not session:
            return "Session not found."
        new_start = datetime.fromisoformat(tool_args["new_start_time"])
        duration  = session.end_time - session.start_time
        session.start_time = new_start
        session.end_time   = new_start + duration
        db.commit()
        return f"Session moved to {new_start.strftime('%a %b %d at %H:%M')}."

    return "Unknown tool."
```

---

### Step 4: Chat Route (The Agent Loop)

This is the core of Phase 2. It runs the LLM ↔ tool loop until the model produces a final text response.

**`routes/chat.py`**
```python
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import os, json
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from models import ChatMessage, UserMemory, UserPreferences
from llm.tools import TOOLS
from llm.tool_executor import execute_tool
from db import get_db

router = APIRouter(prefix="/chat")
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def build_chat_system_prompt(user_id: str) -> str:
    db    = get_db()
    prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
    
    # Fetch recent memories
    memories = db.query(UserMemory).order_by(
        UserMemory.last_referenced_at.desc()
    ).limit(10).all()
    memory_text = "\n".join(f"- {m.content}" for m in memories) or "None yet."
    
    return f"""You are tempo, a helpful study scheduling assistant.
You help students manage their study schedules by adding tasks, 
moving sessions, blocking time, and answering questions about their plan.

IMPORTANT RULES:
- Always use the get_schedule tool before answering questions about 
  specific times or what is scheduled when.
- If information is missing to add a task (no deadline, no hours estimate),
  use ask_clarification to get exactly what you need. Ask ONE thing at a time.
- When the user mentions something that should be remembered 
  (e.g. a recurring commitment, a stated preference, a struggle with a subject),
  acknowledge it naturally. It will be stored automatically.
- Today's date is {datetime.utcnow().date().isoformat()}.
- After using a tool that modifies the schedule, tell the user briefly 
  what you did and that their schedule is updating.

USER PREFERENCES:
- Working hours: {prefs.day_start} to {prefs.day_end}
- Available days: {prefs.available_days}
- Max sessions per day: {prefs.max_sessions_per_day}

THINGS TO REMEMBER ABOUT THIS USER:
{memory_text}
"""

class ChatRequest(BaseModel):
    message: str
    history: list = []   # [{role, content}] from frontend

@router.post("/")
def chat(body: ChatRequest):
    db = get_db()
    
    system_prompt = build_chat_system_prompt("user_1")
    
    # Convert tool definitions to Gemini format
    gemini_tools = [
        Tool(function_declarations=[
            FunctionDeclaration(
                name        = t["name"],
                description = t["description"],
                parameters  = t["parameters"]
            ) for t in TOOLS
        ])
    ]
    
    model = genai.GenerativeModel(
        model_name     = "gemini-2.0-flash",
        system_instruction = system_prompt,
        tools          = gemini_tools
    )
    
    # Build message history for multi-turn context
    history = body.history or []
    
    # Append current user message
    messages = history + [{"role": "user", "parts": [body.message]}]
    
    # --- Agent loop ---
    # Keep calling the model until it produces a text response
    # (no more tool calls pending)
    max_iterations = 5
    tool_calls_log = []
    
    for _ in range(max_iterations):
        response = model.generate_content(messages)
        candidate = response.candidates[0]
        
        # Check if model wants to call a tool
        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if hasattr(part, 'function_call') and part.function_call
        ]
        
        if not function_calls:
            # Model produced a final text response — we're done
            final_text = "".join(
                part.text for part in candidate.content.parts
                if hasattr(part, 'text')
            )
            break
        
        # Execute each tool call and feed results back
        tool_results = []
        for fc in function_calls:
            result = execute_tool(fc.name, dict(fc.args))
            tool_calls_log.append({
                "tool":   fc.name,
                "args":   dict(fc.args),
                "result": result
            })
            tool_results.append({
                "role": "tool",
                "parts": [{
                    "function_response": {
                        "name":     fc.name,
                        "response": {"result": result}
                    }
                }]
            })
        
        # Append model response + tool results to message history
        messages.append({"role": "model", "parts": candidate.content.parts})
        messages.extend(tool_results)
    
    else:
        final_text = "I'm having trouble completing that request. Could you rephrase?"
    
    # Persist messages to DB
    db.add(ChatMessage(
        role       = "user",
        content    = body.message,
        created_at = datetime.utcnow()
    ))
    db.add(ChatMessage(
        role       = "assistant",
        content    = final_text,
        tool_calls = tool_calls_log,
        created_at = datetime.utcnow()
    ))
    db.commit()
    
    # Trigger background memory extraction
    extract_memories_from_message.delay(body.message)
    
    return {
        "reply":      final_text,
        "tool_calls": tool_calls_log
    }
```

---

### Step 5: Memory Extraction (Background Job)

After every user message, a cheap background LLM call checks for persistent facts to store.

**`jobs/memory_extractor.py`**
```python
import google.generativeai as genai
import json, os
from datetime import datetime
from models import UserMemory
from db import get_db

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

EXTRACTION_PROMPT = """
Extract any NEW persistent facts about the user from this message.
Return ONLY a JSON array. Return an empty array [] if there is nothing new.
Each fact should have: "content" (string), "type" ("constraint"|"preference"|"context").

Examples of things to extract:
- Recurring commitments: "I have football every Thursday at 7pm"
- Stated struggles: "I always find calculus hard"
- Personal preferences: "I prefer doing hard tasks in the morning"
- Life context: "I work part time on Saturdays"

Do NOT extract things that are already one-off task requests 
(those are handled separately). 
Return raw JSON only, no backticks, no explanation.
"""

def extract_memories_from_message(message: str):
    response = model.generate_content(
        EXTRACTION_PROMPT + f"\n\nUser message: \"{message}\""
    )
    
    try:
        facts = json.loads(response.text.strip())
    except json.JSONDecodeError:
        return  # nothing to extract
    
    if not facts:
        return
    
    db = get_db()
    existing = [m.content for m in db.query(UserMemory).all()]
    
    for fact in facts:
        # Simple dedup: skip if very similar content already exists
        content = fact.get("content","").strip()
        if not content:
            continue
        if any(content.lower() in e.lower() or e.lower() in content.lower()
               for e in existing):
            continue
        db.add(UserMemory(
            content            = content,
            memory_type        = fact.get("type", "context"),
            created_at         = datetime.utcnow(),
            last_referenced_at = datetime.utcnow()
        ))
    db.commit()
```

---

### Step 6: Chat UI (Frontend)

**`components/ChatPanel.jsx`**
```jsx
import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I can help you manage your study schedule. Try adding a task or asking what\'s coming up this week.' }
  ])
  const [input, setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    // Build history for context (last 10 messages, excluding system)
    const history = messages.slice(-10).map(m => ({
      role:  m.role === 'assistant' ? 'model' : 'user',
      parts: [m.content]
    }))

    try {
      const { data } = await axios.post('/api/chat', {
        message: userMsg,
        history
      })
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong — please try again.'
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <p>{m.content}</p>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <p className="thinking">Thinking...</p>
          </div>
        )}
        <div ref={bottomRef}/>
      </div>

      <div className="chat-input">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Add a task, move a session, ask a question..."
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
```

---

### Phase 2 Completion Checklist

```
[ ] chat_messages and user_memories tables migrated
[ ] Tool definitions cover: add_task, move_session, block_time,
    get_schedule, update_preference, ask_clarification
[ ] Tool executor handles all tool types and returns string results
[ ] Agent loop correctly handles multi-step tool call chains
[ ] Memory extraction job runs after every user message
[ ] Extracted memories appear in system prompt on subsequent calls
[ ] Chat UI sends message history for multi-turn context
[ ] "Add a task via chat" end-to-end works: message → tool call → 
    DB write → solver re-run → updated schedule view
[ ] Relative dates ("next Friday") correctly resolved to absolute dates
[ ] Clarification questions fire when task fields are missing
[ ] Tool calls logged in chat_messages.tool_calls for auditability
```

---

## Project Structure (End of Phase 2)

```
tempo/
├── backend/
│   ├── main.py                  # FastAPI app, registers all routers
│   ├── models.py                # SQLAlchemy models
│   ├── db.py                    # DB session management
│   ├── solver/
│   │   └── scheduler.py         # OR-Tools CP-SAT solver
│   ├── scheduling/
│   │   └── context_builder.py   # Assembles SchedulingRequest from DB
│   ├── llm/
│   │   ├── explainer.py         # Post-schedule LLM explanation call
│   │   ├── tools.py             # Tool schema definitions
│   │   └── tool_executor.py     # Executes tool calls against DB
│   ├── jobs/
│   │   ├── reschedule.py        # Full pipeline: context → solver → explain → write
│   │   └── memory_extractor.py  # Background memory extraction
│   └── routes/
│       ├── tasks.py
│       ├── sessions.py
│       ├── preferences.py
│       └── chat.py
│
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── ScheduleView.jsx
│       │   ├── SessionCard.jsx
│       │   ├── AddTaskForm.jsx
│       │   ├── ChatPanel.jsx
│       │   └── Onboarding.jsx
│       └── api/
│           └── client.js        # axios instance, base URL config
│
├── alembic/                     # DB migrations
├── .env
└── requirements.txt
```

---

## Common Failure Modes to Watch For

**Solver produces infeasible result after a minor change.** Usually means the remaining hours estimate is wrong — check `sum_completed_session_minutes` logic. Add logging to the context builder to print the scheduling request before each solver run.

**Gemini tool calls missing required fields.** The clarification tool exists for this, but Gemini will sometimes attempt a tool call with missing args anyway. Add a validation step in the tool executor that checks required fields before executing and returns an error string back to the model if something is missing.

**Memory extraction storing noise.** The extraction prompt will occasionally pull in task-specific information as a memory (e.g. "User has a calculus exam on May 18th"). Add a filter in the extractor: skip any fact that contains a specific one-off date, as those are task data, not memory data.

**Chat history growing too long.** Gemini has context limits. Cap the history you send at 20 messages. For longer conversations, summarise older history into a single context block rather than sending raw messages.

**Schedule view not refreshing after a chat-triggered reschedule.** The reschedule job is async — the chat route returns before the new schedule is written. Either poll the schedule endpoint after a tool call response, or use a WebSocket to push an invalidation event to the frontend when the job completes.