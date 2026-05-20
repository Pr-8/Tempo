# Tempo — Gemini CLI Build Guide
### Step-by-step prompts with manual verification tests

Each step includes:
- A **Gemini CLI prompt** to paste directly
- A **test script or command** to verify the step works
- A **pass/fail checklist** you can check manually

Run each step, verify it passes, then move to the next. Do not proceed if a step fails.

---

## Prerequisites

```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Auth
gemini auth login

# Create project
mkdir tempo && cd tempo
mkdir -p backend/{solver,scheduling,llm,jobs,routes} frontend/src/components frontend/src/api
```

---

---

# PHASE 1 — CORE SCHEDULING LOOP

---

## Step 1 — Project scaffold & environment

**Prompt:**
```
Create the following project structure for a Python/FastAPI backend called "tempo":

1. backend/requirements.txt with these exact packages:
   fastapi uvicorn sqlalchemy alembic psycopg2-binary
   google-generativeai ortools redis rq python-dotenv pydantic rapidfuzz

2. backend/.env.example with these variables (empty values):
   DATABASE_URL=
   GEMINI_API_KEY=
   REDIS_URL=
   PLANNING_HORIZON_DAYS=21

3. backend/db.py that:
   - Reads DATABASE_URL from environment using python-dotenv
   - Creates a SQLAlchemy engine and SessionLocal
   - Exposes a get_db() function that returns a db session
   - Exposes a get_db_context() context manager for use in background jobs

4. backend/main.py that:
   - Creates a FastAPI app
   - Has a GET /health endpoint that returns {"status": "ok"}
   - Loads .env on startup

Write clean, minimal, production-ready code. No placeholder comments.
```

**Test:**
```bash
cd backend
cp .env.example .env
# Fill in a test DATABASE_URL (SQLite is fine for local dev):
echo "DATABASE_URL=sqlite:///./tempo_test.db" >> .env
pip install -r requirements.txt
uvicorn main:app --reload &
sleep 2
curl http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

**Pass criteria:**
- [ ] `curl /health` returns `{"status":"ok"}`
- [ ] No import errors on startup

---

## Step 2 — Database models

**Prompt:**
```
Create backend/models.py for the Tempo app with these SQLAlchemy models.
Use declarative_base. Use PostgreSQL UUID type (sqlalchemy.dialects.postgresql.UUID)
with fallback to String for SQLite compatibility — wrap UUID columns as:
  Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

Models:

1. TaskStatus enum: pending, complete, failed
2. SessionStatus enum: pending, complete, failed

3. Task table (tasks):
   id, title (String, not null), course (String, nullable),
   estimated_hours (Float, not null), deadline (Date, not null),
   priority (String, default "medium"), status (String, default "pending"),
   source (String, default "manual"), created_at (DateTime)

4. ScheduledSession table (scheduled_sessions):
   id, task_id (String, not null, FK to tasks.id), start_time (DateTime),
   end_time (DateTime), status (String, default "pending"),
   failed_at (DateTime, nullable)

5. UserPreferences table (user_preferences):
   id, user_id (String, unique, not null),
   available_days (String, default "mon,tue,wed,thu,fri"),
   day_start (String, default "09:00"), day_end (String, default "18:00"),
   max_sessions_per_day (Integer, default 3),
   min_break_minutes (Integer, default 30),
   preferred_session_mins (Integer, default 60),
   max_session_mins (Integer, default 120),
   schedule_dirty (Boolean, default False),
   blocked_dates (String, default ""),
   last_schedule_explanation (String, nullable)

Use String enums (not SQLAlchemy Enum type) for max SQLite compatibility.
Import Integer from sqlalchemy.
```

**Test:**
```bash
cd backend
python - <<'EOF'
from sqlalchemy import create_engine
from models import Base, Task, ScheduledSession, UserPreferences
import datetime, uuid

engine = create_engine("sqlite:///./test_models.db")
Base.metadata.create_all(engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
db = Session()

# Create a test task
t = Task(
    title="Test Task",
    estimated_hours=2.0,
    deadline=datetime.date.today() + datetime.timedelta(days=7),
    priority="high",
    created_at=datetime.datetime.utcnow()
)
db.add(t)
db.commit()
db.refresh(t)

# Create preferences
p = UserPreferences(user_id="user_1")
db.add(p)
db.commit()

assert db.query(Task).count() == 1
assert db.query(UserPreferences).count() == 1
print("PASS: models created and queried successfully")
print(f"  Task id: {t.id}, title: {t.title}")

import os
os.remove("test_models.db")
EOF
```

**Pass criteria:**
- [ ] Script prints `PASS`
- [ ] No SQLAlchemy errors
- [ ] Task and UserPreferences rows inserted and queryable

---

## Step 3 — Constraint solver (the most critical component)

**Prompt:**
```
Create backend/solver/__init__.py (empty) and backend/solver/scheduler.py.

The scheduler must implement:

1. SLOT_MINUTES = 30 constant

2. generate_slots(start_date, horizon_days, available_days, day_start, day_end) -> List[Dict]
   - Returns list of {"index": int, "dt": datetime} for every 30-min slot
     across the planning horizon on available days between day_start and day_end
   - available_days is a list of strings: ["mon","tue","wed","thu","fri"]
   - day_start / day_end are "HH:MM" strings

3. solve_schedule(scheduling_request: dict) -> dict
   Input shape:
   {
     "tasks": [{"id", "title", "remaining_hours", "deadline" (YYYY-MM-DD), "priority"}],
     "constraints": {
       "available_windows": [{"days": [...], "start": "HH:MM", "end": "HH:MM"}],
       "blocked_dates": ["YYYY-MM-DD"],
       "session_rules": {
         "min_session_minutes": int,
         "max_session_minutes": int,
         "preferred_session_minutes": int,
         "min_break_between_sessions": int,
         "max_sessions_per_day": int
       }
     },
     "planning_horizon_days": int
   }

   Uses OR-Tools CP-SAT solver to:
   - Break each task into fixed-length sessions (use preferred_session_minutes,
     clamped to [min, max])
   - Enforce no overlap between sessions (AddNoOverlap)
   - Enforce all sessions for a task finish before its deadline
   - Enforce sessions of the same task are ordered with min_break_between_sessions gap
   - Enforce max sessions per day using BoolVar per session per day
   - Minimise sum of (priority_weight * start_var) — schedule high-priority tasks earlier
     (priority weights: high=3, medium=2, low=1)
   - Set solver time limit to 10 seconds

   Returns on success:
   {"status": "OPTIMAL"|"FEASIBLE", "solve_time_ms": int,
    "scheduled_sessions": [{"task_id", "start": ISO, "end": ISO}],
    "unschedulable_tasks": []}

   Returns on failure:
   {"status": "INFEASIBLE", "solve_time_ms": int,
    "scheduled_sessions": [], "unschedulable_tasks": [task_id, ...]}

Use from ortools.sat.python import cp_model
Use from datetime import datetime, timedelta, date
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys
sys.path.insert(0, ".")
from solver.scheduler import solve_schedule, generate_slots
from datetime import date, timedelta

# --- Test 1: generate_slots ---
slots = generate_slots(date.today(), 5, ["mon","tue","wed","thu","fri"], "09:00", "11:00")
slots_per_day = 4  # 09:00, 09:30, 10:00, 10:30
print(f"Slots generated: {len(slots)} (expected ~{slots_per_day} per weekday over 5 days)")
assert len(slots) > 0, "No slots generated"
assert slots[0]["index"] == 0
assert "dt" in slots[0]

# --- Test 2: basic solve ---
result = solve_schedule({
    "planning_horizon_days": 14,
    "tasks": [
        {
            "id": "t1",
            "title": "Calculus Revision",
            "remaining_hours": 2.0,
            "deadline": (date.today() + timedelta(days=7)).isoformat(),
            "priority": "high"
        },
        {
            "id": "t2",
            "title": "Physics Problem Set",
            "remaining_hours": 1.5,
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
            "min_session_minutes": 30,
            "max_session_minutes": 120,
            "preferred_session_minutes": 60,
            "min_break_between_sessions": 30,
            "max_sessions_per_day": 3
        }
    }
})

assert result["status"] in ("OPTIMAL", "FEASIBLE"), f"Expected OPTIMAL/FEASIBLE, got {result['status']}"
sessions = result["scheduled_sessions"]
assert len(sessions) > 0, "No sessions scheduled"

# Verify no overlaps
sorted_sessions = sorted(sessions, key=lambda s: s["start"])
for i in range(len(sorted_sessions) - 1):
    from datetime import datetime
    end_i   = datetime.fromisoformat(sorted_sessions[i]["end"])
    start_j = datetime.fromisoformat(sorted_sessions[i+1]["start"])
    assert end_i <= start_j, f"Overlap detected between session {i} and {i+1}"

# Verify deadlines respected
for s in sessions:
    task_deadline = (date.today() + timedelta(days=7)).isoformat() if s["task_id"] == "t1" \
                    else (date.today() + timedelta(days=10)).isoformat()
    from datetime import datetime
    session_end_date = datetime.fromisoformat(s["end"]).date().isoformat()
    assert session_end_date <= task_deadline, \
        f"Session for {s['task_id']} ends {session_end_date} after deadline {task_deadline}"

print(f"PASS: Solver returned {result['status']} with {len(sessions)} sessions")
for s in sessions:
    print(f"  {s['task_id']}: {s['start'][:16]} → {s['end'][11:16]}")

# --- Test 3: infeasible (1-hour task, deadline today) ---
result_inf = solve_schedule({
    "planning_horizon_days": 1,
    "tasks": [{
        "id": "t_impossible",
        "title": "Impossible",
        "remaining_hours": 100.0,
        "deadline": date.today().isoformat(),
        "priority": "high"
    }],
    "constraints": {
        "available_windows": [{"days": ["mon","tue","wed","thu","fri"], "start": "09:00", "end": "10:00"}],
        "blocked_dates": [],
        "session_rules": {
            "min_session_minutes": 30, "max_session_minutes": 60,
            "preferred_session_minutes": 60, "min_break_between_sessions": 30,
            "max_sessions_per_day": 1
        }
    }
})
assert result_inf["status"] == "INFEASIBLE", f"Expected INFEASIBLE, got {result_inf['status']}"
print(f"PASS: Infeasible case correctly identified as INFEASIBLE")
EOF
```

**Pass criteria:**
- [ ] Generates slots correctly
- [ ] Returns OPTIMAL or FEASIBLE for solvable input
- [ ] Zero session overlaps in output
- [ ] All sessions end before their task deadlines
- [ ] Returns INFEASIBLE for impossible input

---

## Step 4 — Context builder

**Prompt:**
```
Create backend/scheduling/__init__.py (empty) and backend/scheduling/context_builder.py.

Implement build_scheduling_request(user_id: str, db) -> dict

It should:
1. Query UserPreferences for user_id (raise ValueError if not found)
2. Query all Tasks with status == "pending"
3. For each pending task, compute remaining_hours:
   - Query ScheduledSession for that task_id where status == "complete"
   - completed_mins = sum of (end_time - start_time).seconds / 60 for each completed session
   - remaining_hrs = max(0, task.estimated_hours - completed_mins / 60)
   - Skip the task if remaining_hrs <= 0
4. Build and return the SchedulingRequest dict matching the solver's expected input:
   {
     "planning_horizon_days": 21,
     "tasks": [...],
     "constraints": {
       "available_windows": [{"days": [...], "start": ..., "end": ...}],
       "blocked_dates": [list of non-empty strings from prefs.blocked_dates.split(",")],
       "session_rules": {
         "min_session_minutes": 45,
         "max_session_minutes": prefs.max_session_mins,
         "preferred_session_minutes": prefs.preferred_session_mins,
         "min_break_between_sessions": prefs.min_break_minutes,
         "max_sessions_per_day": prefs.max_sessions_per_day
       }
     }
   }

Import Task, TaskStatus, ScheduledSession, SessionStatus, UserPreferences from models.
Take db as a parameter (do not call get_db() internally).
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys, datetime
sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task, ScheduledSession, UserPreferences

engine = create_engine("sqlite:///./test_cb.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

# Seed data
prefs = UserPreferences(
    user_id="user_1",
    available_days="mon,tue,wed,thu,fri",
    day_start="09:00", day_end="18:00",
    max_sessions_per_day=3, min_break_minutes=30,
    preferred_session_mins=60, max_session_mins=120
)
db.add(prefs)

task = Task(
    title="Test Task",
    estimated_hours=3.0,
    deadline=datetime.date.today() + datetime.timedelta(days=10),
    priority="high",
    status="pending",
    created_at=datetime.datetime.utcnow()
)
db.add(task)
db.commit()
db.refresh(task)

# Add a completed session (1 hour done)
completed = ScheduledSession(
    task_id=task.id,
    start_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    end_time=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
    status="complete"
)
db.add(completed)
db.commit()

from scheduling.context_builder import build_scheduling_request
req = build_scheduling_request("user_1", db)

assert req["planning_horizon_days"] == 21
assert len(req["tasks"]) == 1
t = req["tasks"][0]
assert t["remaining_hours"] == 2.0, f"Expected 2.0 remaining, got {t['remaining_hours']}"
assert t["priority"] == "high"
assert "available_windows" in req["constraints"]
assert req["constraints"]["session_rules"]["max_session_minutes"] == 120

print(f"PASS: context builder works correctly")
print(f"  remaining_hours: {t['remaining_hours']} (should be 2.0 — 1hr already completed)")
print(f"  available_days: {req['constraints']['available_windows'][0]['days']}")

import os
db.close()
os.remove("test_cb.db")
EOF
```

**Pass criteria:**
- [ ] Remaining hours correctly deducts completed session time
- [ ] Returns correct scheduling request shape
- [ ] Blocked dates list is correctly parsed

---

## Step 5 — Gemini explainer

**Prompt:**
```
Create backend/llm/__init__.py (empty) and backend/llm/explainer.py.

Implement generate_schedule_explanation(solver_output: dict, tasks: list) -> str

It should:
1. Configure google.generativeai with GEMINI_API_KEY from environment
2. Use model "gemini-2.0-flash"
3. Build a prompt that includes:
   - A system instruction telling the model it is a practical study coach
     writing 3-4 sentences explaining: what was prioritised first and why,
     any heavy days or pressure points, any tasks that could NOT be scheduled.
     Be direct. Plain English. No bullet points. Address as "you".
     Do NOT repeat the schedule — only flag things worth knowing.
   - A user message containing:
     - SCHEDULED SESSIONS: one line per session "- {title}: {start} to {end}"
     - TASKS THAT COULD NOT BE SCHEDULED: titles or "None — all tasks fit."
     - TASK DETAILS: JSON with title, deadline, priority, remaining_hours
4. Return response.text.strip()
5. On any exception, return "Schedule updated successfully." as a fallback

Read GEMINI_API_KEY from os.environ (load dotenv at top of file).
```

**Test:**
```bash
cd backend
# Requires a real GEMINI_API_KEY in .env
python - <<'EOF'
import sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("SKIP: No GEMINI_API_KEY set — set it in .env to run this test")
    sys.exit(0)

from llm.explainer import generate_schedule_explanation
from datetime import date, timedelta

solver_output = {
    "status": "OPTIMAL",
    "scheduled_sessions": [
        {"task_id": "t1", "start": "2026-05-15T09:00:00", "end": "2026-05-15T10:00:00"},
        {"task_id": "t2", "start": "2026-05-16T09:00:00", "end": "2026-05-16T10:00:00"},
    ],
    "unschedulable_tasks": []
}
tasks = [
    {"id": "t1", "title": "Calculus Revision", "deadline": (date.today()+timedelta(days=7)).isoformat(),
     "priority": "high", "remaining_hours": 2.0},
    {"id": "t2", "title": "Physics Problem Set", "deadline": (date.today()+timedelta(days=10)).isoformat(),
     "priority": "medium", "remaining_hours": 1.5},
]

explanation = generate_schedule_explanation(solver_output, tasks)

assert isinstance(explanation, str), "Expected string return"
assert len(explanation) > 20, f"Explanation too short: {repr(explanation)}"
# Should not just be the fallback (unless API failed)
print(f"PASS: Explainer returned {len(explanation)} chars")
print(f"  Preview: {explanation[:200]}...")
EOF
```

**Pass criteria:**
- [ ] Returns a non-empty string
- [ ] Explanation mentions at least one task name or scheduling detail
- [ ] Does not crash — falls back gracefully if API unavailable

---

## Step 6 — Reschedule pipeline job

**Prompt:**
```
Create backend/jobs/__init__.py (empty) and backend/jobs/reschedule.py.

Implement:

1. run_reschedule_pipeline(user_id: str)
   - Creates a DB session using get_db_context() from db.py
   - Calls build_scheduling_request(user_id, db) — if no tasks, return early
   - Calls solve_schedule(scheduling_request)
   - Deletes all ScheduledSession rows with status == "pending" for this user's tasks
     (get all task_ids from the scheduling_request, delete sessions for those task_ids)
   - Inserts new ScheduledSession rows from solver_output["scheduled_sessions"]
   - Calls generate_schedule_explanation(solver_output, scheduling_request["tasks"])
   - Updates UserPreferences: last_schedule_explanation = explanation, schedule_dirty = False
   - Commits and returns solver_output

2. mark_schedule_dirty(user_id: str)
   - Tries to enqueue run_reschedule_pipeline via RQ
   - If Redis is unavailable, falls back to running run_reschedule_pipeline synchronously
   - Import Queue from rq, Redis from redis
   - Catch connection errors gracefully

Import paths:
  from scheduling.context_builder import build_scheduling_request
  from solver.scheduler import solve_schedule
  from llm.explainer import generate_schedule_explanation
  from db import get_db_context
  from models import ScheduledSession, SessionStatus, UserPreferences
  from datetime import datetime
  import os
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys, os, datetime
sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pipeline.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("GEMINI_API_KEY", "test_key_placeholder")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task, UserPreferences, ScheduledSession

engine = create_engine("sqlite:///./test_pipeline.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

prefs = UserPreferences(
    user_id="user_1",
    available_days="mon,tue,wed,thu,fri",
    day_start="09:00", day_end="18:00",
    max_sessions_per_day=3, min_break_minutes=30,
    preferred_session_mins=60, max_session_mins=120
)
db.add(prefs)

task = Task(
    title="Pipeline Test Task",
    estimated_hours=2.0,
    deadline=datetime.date.today() + datetime.timedelta(days=14),
    priority="medium",
    status="pending",
    created_at=datetime.datetime.utcnow()
)
db.add(task)
db.commit()
db.close()

# Patch db.py to use test DB
import db as db_module
from sqlalchemy.orm import sessionmaker as SM
test_engine = create_engine("sqlite:///./test_pipeline.db")
from contextlib import contextmanager
@contextmanager
def test_db_context():
    s = SM(bind=test_engine)()
    try:
        yield s
        s.commit()
    finally:
        s.close()
db_module.get_db_context = test_db_context

from jobs.reschedule import run_reschedule_pipeline
result = run_reschedule_pipeline("user_1")

assert result is not None, "Pipeline returned None"
assert result["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE"), f"Unexpected status: {result}"

# Verify sessions were written
check_session = SM(bind=test_engine)()
session_count = check_session.query(ScheduledSession).count()
prefs_check = check_session.query(UserPreferences).filter_by(user_id="user_1").first()
check_session.close()

if result["status"] in ("OPTIMAL", "FEASIBLE"):
    assert session_count > 0, "No sessions written to DB"
    print(f"PASS: Pipeline wrote {session_count} sessions")
else:
    print(f"PASS: Pipeline ran (INFEASIBLE — no sessions written, which is correct)")

print(f"  schedule_dirty reset: {prefs_check.schedule_dirty == False}")

import os as _os
_os.remove("test_pipeline.db")
EOF
```

**Pass criteria:**
- [ ] Pipeline runs without error
- [ ] Sessions written to DB after successful solve
- [ ] `schedule_dirty` reset to False
- [ ] Graceful fallback if Redis not running

---

## Step 7 — FastAPI routes

**Prompt:**
```
Create the following FastAPI route files. Each file uses a `db` session from get_db()
and a constant HARDCODED_USER_ID = "user_1".

backend/routes/__init__.py — empty

backend/routes/tasks.py — APIRouter with prefix "/tasks":
  POST /          — create task (title, course?, estimated_hours, deadline, priority="medium")
                    Validate: estimated_hours > 0 and <= 40; deadline must be in the future
                    Create Task, commit, call mark_schedule_dirty(HARDCODED_USER_ID), return task as dict
  GET /           — list all tasks ordered by deadline, return list of dicts
  DELETE /{id}    — delete task by UUID string, 404 if not found, trigger reschedule, return {"ok": True}

backend/routes/sessions.py — APIRouter with prefix="/sessions":
  GET /                       — list pending sessions ordered by start_time, return list of dicts
  PATCH /{id}/complete        — mark session complete; if no more pending sessions for that task,
                                mark the task as complete too; return {"ok": True}
  PATCH /{id}/failed          — mark session failed with failed_at=utcnow(); trigger reschedule;
                                return {"ok": True, "message": "Rescheduling..."}

backend/routes/preferences.py — APIRouter with prefix="/preferences":
  GET /   — return current prefs for HARDCODED_USER_ID as dict (create default if not found)
  PUT /   — update prefs (available_days list, day_start, day_end, max_sessions_per_day,
            min_break_minutes, preferred_session_mins, max_session_mins)
            Save available_days as comma-separated string. Trigger reschedule.

Update backend/main.py to:
  - Import and register all three routers with prefix "/api"
  - Add CORS middleware allowing all origins (for local dev)

For returning SQLAlchemy models as dicts, use a helper:
  def row_to_dict(row): return {c.name: getattr(row, c.name) for c in row.__table__.columns}
Convert date/datetime fields to .isoformat() in the dict.
```

**Test:**
```bash
cd backend
# Start the server with SQLite for testing
DATABASE_URL=sqlite:///./test_routes.db uvicorn main:app --reload --port 8001 &
sleep 3

# Seed preferences (required before tasks can be scheduled)
curl -s -X PUT http://localhost:8001/api/preferences \
  -H "Content-Type: application/json" \
  -d '{"available_days":["mon","tue","wed","thu","fri"],"day_start":"09:00","day_end":"18:00","max_sessions_per_day":3,"min_break_minutes":30,"preferred_session_mins":60,"max_session_mins":120}' | python3 -m json.tool

# Create a task
DEADLINE=$(python3 -c "from datetime import date,timedelta; print((date.today()+timedelta(days=14)).isoformat())")
curl -s -X POST http://localhost:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Test Task\",\"estimated_hours\":2.0,\"deadline\":\"$DEADLINE\",\"priority\":\"high\"}" | python3 -m json.tool

# List tasks — should see the task
curl -s http://localhost:8001/api/tasks | python3 -m json.tool

# List sessions (may be empty if Redis/RQ not running — that's OK)
curl -s http://localhost:8001/api/sessions | python3 -m json.tool

# Test validation — deadline in the past should fail
curl -s -X POST http://localhost:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Bad Task","estimated_hours":2.0,"deadline":"2020-01-01","priority":"high"}' | python3 -m json.tool
# Expected: 400 error

kill %1
sleep 1
rm -f test_routes.db
```

**Pass criteria:**
- [ ] PUT /preferences returns `{"ok": true}`
- [ ] POST /tasks creates and returns a task with an `id` field
- [ ] GET /tasks returns a list containing the created task
- [ ] POST /tasks with past deadline returns HTTP 400
- [ ] GET /sessions returns a list (empty is fine at this stage)

---

## Step 8 — Alembic migrations (PostgreSQL setup)

**Prompt:**
```
Write the commands and configuration needed to set up Alembic for the Tempo backend.

Produce:
1. The exact shell commands to run (alembic init, etc.)
2. The content to add to alembic/env.py to:
   - Load DATABASE_URL from .env using python-dotenv
   - Set config.set_main_option("sqlalchemy.url", DATABASE_URL)
   - Import Base from models and set target_metadata = Base.metadata
3. The line to add/change in alembic.ini for the script location
4. The commands to create and run the initial migration

Also note: for production, replace sqlite:/// with postgresql:// in .env
```

**Test:**
```bash
# With PostgreSQL running and .env configured:
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# Verify tables exist:
python3 - <<'EOF'
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv
import os
load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"])
inspector = inspect(engine)
tables = inspector.get_table_names()
expected = {"tasks", "scheduled_sessions", "user_preferences"}
missing = expected - set(tables)
assert not missing, f"Missing tables: {missing}"
print(f"PASS: All tables present: {tables}")
EOF
```

**Pass criteria:**
- [ ] `alembic upgrade head` runs without error
- [ ] All three tables exist in the database
- [ ] `alembic current` shows the migration as applied

---

## Step 9 — Frontend scaffold + ScheduleView

**Prompt:**
```
Create a React frontend for Tempo using Vite. Produce these files:

frontend/src/api/client.js:
  - axios instance with baseURL from import.meta.env.VITE_API_URL or "http://localhost:8000"

frontend/src/components/ScheduleView.jsx:
  - Use FullCalendar (timeGridPlugin, timeGridWeek view)
  - Fetch sessions from GET /api/sessions and tasks from GET /api/tasks using axios
  - Map sessions to FullCalendar events: title = task title, start/end from session
  - For each event, render a small card showing: task title, course (if any),
    a coloured dot by priority (red=high, amber=medium, green=low),
    a "✓ Done" button (PATCH /api/sessions/:id/complete),
    a "✗ Failed" button (PATCH /api/sessions/:id/failed)
  - After marking done/failed, refetch sessions and tasks
  - Show a read-only LLM explanation banner at the top if available
    (fetch from GET /api/preferences, display prefs.last_schedule_explanation)
  - Use React hooks (useState, useEffect) — no external state library

frontend/src/components/AddTaskForm.jsx:
  - Form fields: title (text), course (text, optional), estimated_hours (number),
    deadline (date), priority (select: low/medium/high)
  - On submit: POST /api/tasks, clear form, call onTaskAdded callback prop

frontend/src/App.jsx:
  - Two-column layout: left = AddTaskForm + task list, right = ScheduleView
  - Fetch and display task list (title, deadline, priority, status) from GET /api/tasks
  - When a task is added or deleted, refetch task list and schedule

frontend/vite.config.js:
  - Proxy /api to http://localhost:8000 for local development

Produce clean, functional React. No TypeScript. No CSS frameworks — just inline styles
or a minimal App.css. Keep components simple and readable.
```

**Test:**
```bash
cd frontend
npm install
npm run build
# Should complete with no errors

# Manual test: start backend + frontend
# cd ../backend && uvicorn main:app --reload &
# cd ../frontend && npm run dev
# Open http://localhost:5173
# Verify: page loads, "Add Task" form is visible, calendar renders
```

**Pass criteria:**
- [ ] `npm run build` succeeds with no errors
- [ ] App.jsx imports compile without error
- [ ] Calendar renders (even if empty) when backend is running
- [ ] AddTaskForm shows all required fields

---

---

# PHASE 2 — CHAT INTERFACE

**Only proceed after all Phase 1 steps pass.**

---

## Step P2-1 — Extend database models

**Prompt:**
```
Add two new models to backend/models.py:

1. ChatMessage table (chat_messages):
   id (String UUID pk), role (String — "user"|"assistant"|"tool"),
   content (String), tool_calls (String, nullable — store as JSON string),
   created_at (DateTime)

2. UserMemory table (user_memories):
   id (String UUID pk), content (String), memory_type (String — "constraint"|"preference"|"context"),
   created_at (DateTime), last_referenced_at (DateTime)

Also create an Alembic migration:
  alembic revision --autogenerate -m "add chat and memory tables"
  alembic upgrade head
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys, os, datetime
sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p2_models.db")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, ChatMessage, UserMemory

engine = create_engine("sqlite:///./test_p2_models.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

msg = ChatMessage(role="user", content="Hello", created_at=datetime.datetime.utcnow())
db.add(msg)
mem = UserMemory(
    content="User has football every Thursday",
    memory_type="constraint",
    created_at=datetime.datetime.utcnow(),
    last_referenced_at=datetime.datetime.utcnow()
)
db.add(mem)
db.commit()

assert db.query(ChatMessage).count() == 1
assert db.query(UserMemory).count() == 1
print("PASS: ChatMessage and UserMemory models work correctly")

import os as _os
db.close()
_os.remove("test_p2_models.db")
EOF
```

**Pass criteria:**
- [ ] Both new tables created
- [ ] Rows can be inserted and queried

---

## Step P2-2 — Tool definitions

**Prompt:**
```
Create backend/llm/tools.py.

Define TOOLS as a Python list of dicts, one per tool:

1. add_task — add a new study task
   Required params: title (string), estimated_hours (number),
                    deadline (string, YYYY-MM-DD), priority (enum: low/medium/high)
   Optional: course (string)

2. move_session — move a session to a new time
   Required: session_id (string), new_start_time (string, ISO datetime)

3. block_time — block a date from being scheduled
   Required: date (string, YYYY-MM-DD)
   Optional: reason (string)

4. get_schedule — get scheduled sessions for a date range
   Required: start_date (string, YYYY-MM-DD), end_date (string, YYYY-MM-DD)

5. update_preference — update a user preference
   Required: key (string, one of: day_start/day_end/max_sessions_per_day/min_break_minutes),
             value (string)

6. ask_clarification — ask the user ONE clarifying question
   Required: question (string)

Each tool dict has: "name", "description", "parameters" (JSON Schema object shape).
Write clear, specific descriptions — the LLM uses these to decide which tool to call.
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys
sys.path.insert(0, ".")
from llm.tools import TOOLS

assert isinstance(TOOLS, list), "TOOLS must be a list"
assert len(TOOLS) == 6, f"Expected 6 tools, got {len(TOOLS)}"

tool_names = [t["name"] for t in TOOLS]
required_names = {"add_task","move_session","block_time","get_schedule","update_preference","ask_clarification"}
assert set(tool_names) == required_names, f"Missing tools: {required_names - set(tool_names)}"

# Check structure of each tool
for tool in TOOLS:
    assert "name" in tool
    assert "description" in tool and len(tool["description"]) > 10
    assert "parameters" in tool
    assert "properties" in tool["parameters"]
    assert "required" in tool["parameters"]

# Spot-check add_task required fields
add_task = next(t for t in TOOLS if t["name"] == "add_task")
assert "title" in add_task["parameters"]["required"]
assert "deadline" in add_task["parameters"]["required"]
assert "estimated_hours" in add_task["parameters"]["required"]

print(f"PASS: All {len(TOOLS)} tools defined correctly")
for t in TOOLS:
    print(f"  {t['name']}: {len(t['parameters']['required'])} required params")
EOF
```

**Pass criteria:**
- [ ] 6 tools defined
- [ ] Each has name, description, parameters with properties and required
- [ ] `add_task` requires title, estimated_hours, deadline, priority

---

## Step P2-3 — Tool executor

**Prompt:**
```
Create backend/llm/tool_executor.py.

Implement execute_tool(tool_name: str, tool_args: dict, db) -> str
(take db as a parameter, not from get_db())

Handle each tool:

add_task:
  - Validate required fields; return error string if missing
  - Create Task with source="chat", status="pending", created_at=utcnow()
  - Commit, call mark_schedule_dirty("user_1")
  - Return "Task '{title}' added. Schedule is being updated."

move_session:
  - Look up ScheduledSession by id; return "Session not found." if missing
  - Parse new_start_time, preserve duration, update start_time and end_time
  - Commit, return "Session moved to {new time}."

block_time:
  - Get UserPreferences for user_1
  - Add date to blocked_dates (comma-separated string), avoiding duplicates
  - Commit, call mark_schedule_dirty("user_1")
  - Return "Blocked {date}. Schedule is being updated."

get_schedule:
  - Query ScheduledSession with start_time in [start_date, end_date] and status pending
  - For each session, also query its Task
  - Return formatted string of sessions, or "No sessions scheduled in that range."

update_preference:
  - Validate key is one of: day_start, day_end, max_sessions_per_day, min_break_minutes
  - setattr on prefs, commit, call mark_schedule_dirty("user_1")
  - Return "Updated {key} to {value}."

ask_clarification:
  - Return "CLARIFICATION:" + tool_args["question"]
  (the chat route detects this prefix and sends the question directly to the user)

unknown tool:
  - Return "Unknown tool: {tool_name}"

Import mark_schedule_dirty from jobs.reschedule.
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys, os, datetime
sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_executor.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("GEMINI_API_KEY", "test_key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task, ScheduledSession, UserPreferences

engine = create_engine("sqlite:///./test_executor.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

# Seed prefs
db.add(UserPreferences(
    user_id="user_1",
    available_days="mon,tue,wed,thu,fri",
    day_start="09:00", day_end="18:00",
    max_sessions_per_day=3, min_break_minutes=30,
    preferred_session_mins=60, max_session_mins=120
))
db.commit()

# Patch reschedule to be a no-op for this test
import jobs.reschedule as rmod
rmod.mark_schedule_dirty = lambda uid: None

from llm.tool_executor import execute_tool

# Test add_task
deadline = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
result = execute_tool("add_task", {
    "title": "Essay Draft",
    "estimated_hours": 3.0,
    "deadline": deadline,
    "priority": "high"
}, db)
assert "Essay Draft" in result, f"Unexpected result: {result}"
assert db.query(Task).count() == 1

# Test get_schedule (no sessions yet)
result2 = execute_tool("get_schedule", {
    "start_date": datetime.date.today().isoformat(),
    "end_date": (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
}, db)
assert "No sessions" in result2

# Test block_time
result3 = execute_tool("block_time", {"date": "2026-06-01"}, db)
assert "Blocked" in result3
prefs = db.query(UserPreferences).filter_by(user_id="user_1").first()
assert "2026-06-01" in (prefs.blocked_dates or "")

# Test ask_clarification
result4 = execute_tool("ask_clarification", {"question": "What is the deadline?"}, db)
assert result4.startswith("CLARIFICATION:")

# Test unknown tool
result5 = execute_tool("nonexistent_tool", {}, db)
assert "Unknown" in result5

print("PASS: All tool executor tests passed")
print(f"  add_task: {result}")
print(f"  get_schedule: {result2}")
print(f"  block_time: {result3}")
print(f"  ask_clarification: {result4}")

import os as _os
db.close()
_os.remove("test_executor.db")
EOF
```

**Pass criteria:**
- [ ] `add_task` creates a DB row and returns confirmation
- [ ] `get_schedule` returns "No sessions" when empty
- [ ] `block_time` updates the blocked_dates field
- [ ] `ask_clarification` returns "CLARIFICATION:..." prefix
- [ ] Unknown tool handled gracefully

---

## Step P2-4 — Memory extractor

**Prompt:**
```
Create backend/jobs/memory_extractor.py.

Implement extract_memories_from_message(message: str, db) -> None

It should:
1. Call Gemini API (gemini-2.0-flash) with a prompt that instructs the model to:
   - Extract NEW persistent facts about the user from the message
   - Return ONLY a JSON array (no backticks, no explanation)
   - Return [] if nothing to extract
   - Each fact: {"content": string, "type": "constraint"|"preference"|"context"}
   - Extract: recurring commitments, stated struggles, preferences, life context
   - Do NOT extract one-off task requests or facts containing specific one-off dates
     (dates like "exam on May 18th" are task data, not memories)
2. Parse the JSON response
3. For each fact, check for near-duplicates in existing UserMemory rows:
   - Skip if content is a substring of any existing memory (case-insensitive)
   - Skip if any existing memory is a substring of the new content
4. Insert new UserMemory rows with created_at and last_referenced_at = utcnow()
5. Commit
6. Handle JSONDecodeError silently (return without saving)
7. Handle API errors gracefully (log and return)

Take db as a parameter.
Read GEMINI_API_KEY from environment.
```

**Test:**
```bash
cd backend
python - <<'EOF'
import sys, os, datetime
sys.path.insert(0, ".")
os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, UserMemory

engine = create_engine("sqlite:///./test_memory.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

if not os.environ.get("GEMINI_API_KEY"):
    print("SKIP: No GEMINI_API_KEY — skipping live API test")
else:
    from jobs.memory_extractor import extract_memories_from_message

    # This should extract a memory
    extract_memories_from_message(
        "By the way, I always struggle with calculus and I have football every Thursday evening.",
        db
    )
    memories = db.query(UserMemory).all()
    print(f"Extracted {len(memories)} memories:")
    for m in memories:
        print(f"  [{m.memory_type}] {m.content}")

    # Run again with same message — should not duplicate
    initial_count = len(memories)
    extract_memories_from_message(
        "I have football every Thursday evening.",
        db
    )
    final_count = db.query(UserMemory).count()
    assert final_count == initial_count, \
        f"Dedup failed: count went from {initial_count} to {final_count}"
    print(f"PASS: Dedup works — count stayed at {final_count}")

    # Should NOT extract a one-off date
    extract_memories_from_message(
        "I have an exam on May 18th for physics.",
        db
    )
    # (hard to assert exactly without knowing what Gemini returns, just check no crash)
    print("PASS: One-off date message did not crash the extractor")

import os as _os
db.close()
_os.remove("test_memory.db")
EOF
```

**Pass criteria:**
- [ ] Extracts memories from a message with recurring commitments
- [ ] Deduplication prevents re-inserting identical memories
- [ ] Does not crash on empty or noise messages

---

## Step P2-5 — Chat route (agent loop)

**Prompt:**
```
Create backend/routes/chat.py.

Implement:

1. build_chat_system_prompt(user_id: str, db) -> str
   - Query UserPreferences for user_id
   - Query top 10 UserMemory rows ordered by last_referenced_at desc
   - Return a system prompt string containing:
     - Role: "You are tempo, a helpful study scheduling assistant"
     - Rules: use get_schedule before answering schedule questions;
              use ask_clarification if deadline/hours missing (one question at a time);
              today's date (datetime.utcnow().date().isoformat())
     - User preferences section (working hours, available days, max sessions)
     - Memories section (list of memory contents, or "None yet.")

2. POST /api/chat
   Input: {message: str, history: list (optional)}
   
   - Build system prompt
   - Convert TOOLS to Gemini FunctionDeclaration/Tool format
   - Build GenerativeModel with system_instruction and tools
   - Construct messages = history + [{role:"user", parts:[message]}]
   
   Agent loop (max 5 iterations):
   - Call model.generate_content(messages)
   - If no function_calls in response → extract text, break
   - For each function_call:
     - Call execute_tool(fc.name, dict(fc.args), db)
     - Log {tool, args, result} to tool_calls_log
     - Build tool result message
   - Append model response + tool results to messages
   - If loop exhausted: final_text = "I'm having trouble with that. Could you rephrase?"
   
   - Persist user and assistant ChatMessage rows to DB
   - Call extract_memories_from_message(body.message, db) (synchronously, not via RQ for simplicity)
   - Return {reply: final_text, tool_calls: tool_calls_log}

Use google.generativeai with GEMINI_API_KEY from environment.
Model: "gemini-2.0-flash"
Import: TOOLS from llm.tools, execute_tool from llm.tool_executor,
        ChatMessage, UserMemory, UserPreferences from models,
        build_chat_system_prompt should be defined in the same file.
```

**Test:**
```bash
cd backend
# Requires GEMINI_API_KEY
python - <<'EOF'
import sys, os, datetime
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("SKIP: No GEMINI_API_KEY")
    sys.exit(0)

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, UserPreferences, ChatMessage

engine = create_engine("sqlite:///./test_chat.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

db.add(UserPreferences(
    user_id="user_1",
    available_days="mon,tue,wed,thu,fri",
    day_start="09:00", day_end="18:00",
    max_sessions_per_day=3, min_break_minutes=30,
    preferred_session_mins=60, max_session_mins=120
))
db.commit()

# Patch executor's reschedule to no-op
import jobs.reschedule as rmod
rmod.mark_schedule_dirty = lambda uid: None

from routes.chat import build_chat_system_prompt

# Test system prompt builds
prompt = build_chat_system_prompt("user_1", db)
assert "tempo" in prompt.lower()
assert "09:00" in prompt
print(f"PASS: System prompt built ({len(prompt)} chars)")

# Test the full route via TestClient
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.chat as chat_route
# Patch db dependency
from unittest.mock import patch

app = FastAPI()
app.include_router(chat_route.router)

client = TestClient(app)

# Override the db in the route by patching get_db
import db as db_module
db_module.get_db = lambda: db

response = client.post("/api/chat", json={
    "message": "What tasks do I have?",
    "history": []
})
assert response.status_code == 200, f"Status {response.status_code}: {response.text}"
data = response.json()
assert "reply" in data
assert isinstance(data["reply"], str)
assert len(data["reply"]) > 5

# Check messages were persisted
msg_count = db.query(ChatMessage).count()
assert msg_count >= 2, f"Expected at least 2 chat messages, got {msg_count}"

print(f"PASS: Chat route returned reply: {data['reply'][:100]}...")
print(f"      Tool calls made: {data['tool_calls']}")
print(f"      Messages persisted: {msg_count}")

import os as _os
db.close()
_os.remove("test_chat.db")
EOF
```

**Pass criteria:**
- [ ] `/api/chat` returns a `reply` string
- [ ] Tool calls logged in response
- [ ] Messages saved to `chat_messages` table
- [ ] System prompt includes user preferences and memories

---

## Step P2-6 — Chat UI

**Prompt:**
```
Create frontend/src/components/ChatPanel.jsx.

A chat interface component:
- State: messages (array of {role, content}), input string, loading boolean
- Initialize messages with one assistant message: "Hi! I'm tempo. I can help you manage
  your study schedule. Try adding a task or asking what's on this week."
- Scroll to bottom after each new message (useRef + useEffect)
- send() function:
  - POST to /api/chat with {message, history}
  - history = last 10 messages mapped to {role: "model"|"user", parts: [content]}
  - Append user message immediately (optimistic), set loading=true
  - On response: append assistant reply
  - On error: append "Something went wrong — please try again."
  - Finally: loading=false
- Render: scrollable message list, input field, Send button
- Enter key triggers send()
- Input and button disabled while loading
- Show "Thinking..." indicator while loading
- Style messages differently by role (user right-aligned, assistant left-aligned)

Export default ChatPanel.

Update frontend/src/App.jsx to include ChatPanel in the layout
(e.g. as a right sidebar or bottom panel alongside the calendar).
```

**Test:**
```bash
cd frontend
npm run build
# Verify no build errors

# Manual test checklist (run npm run dev and open browser):
echo "Manual tests to verify in browser:"
echo "  1. Chat panel renders with initial greeting message"
echo "  2. Typing in input and pressing Enter sends the message"
echo "  3. User message appears right-aligned, assistant left-aligned"
echo "  4. 'Thinking...' indicator appears while waiting"
echo "  5. Reply appears after response"
echo "  6. Adding a task via chat ('Add a task: Essay due next Friday, 3 hours, high priority')"
echo "     should result in a confirmation message"
```

**Pass criteria:**
- [ ] `npm run build` succeeds
- [ ] Chat panel visible in the app
- [ ] Messages display with correct alignment
- [ ] Loading state works

---

---

# END-TO-END INTEGRATION TEST

Run this after all steps are complete to verify the full loop.

**Test:**
```bash
cd backend
python - <<'EOF'
"""
Full end-to-end test of the Tempo core loop (no frontend required).
Requires: GEMINI_API_KEY in .env, SQLite for test isolation.
"""
import sys, os, datetime
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

os.environ["DATABASE_URL"] = "sqlite:///./test_e2e.db"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task, ScheduledSession, UserPreferences, ChatMessage

engine = create_engine("sqlite:///./test_e2e.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

# Setup
prefs = UserPreferences(
    user_id="user_1",
    available_days="mon,tue,wed,thu,fri",
    day_start="09:00", day_end="18:00",
    max_sessions_per_day=3, min_break_minutes=30,
    preferred_session_mins=60, max_session_mins=120
)
db.add(prefs)
db.commit()

print("=== TEMPO END-TO-END TEST ===\n")

# 1. Add a task manually
task = Task(
    title="Linear Algebra Exam Prep",
    estimated_hours=4.0,
    deadline=datetime.date.today() + datetime.timedelta(days=12),
    priority="high",
    status="pending",
    source="manual",
    created_at=datetime.datetime.utcnow()
)
db.add(task)
db.commit()
db.refresh(task)
print(f"[1] Task created: {task.title} (id: {task.id})")

# 2. Run the reschedule pipeline
import jobs.reschedule as rmod
import db as db_module
from contextlib import contextmanager
@contextmanager
def test_db_ctx():
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()
db_module.get_db_context = test_db_ctx
rmod.mark_schedule_dirty = lambda uid: rmod.run_reschedule_pipeline(uid)

result = rmod.run_reschedule_pipeline("user_1")
sessions = db.query(ScheduledSession).filter_by(status="pending").all()
print(f"[2] Solver: {result['status']}, {len(sessions)} sessions scheduled")
assert len(sessions) > 0, "No sessions were scheduled — FAIL"

# 3. Mark the first session complete
first_session = db.query(ScheduledSession).filter_by(status="pending").order_by(
    ScheduledSession.start_time
).first()
first_session.status = "complete"
db.commit()
print(f"[3] Marked session complete: {first_session.start_time} → {first_session.end_time}")

# 4. Re-run pipeline — should have fewer remaining hours
db.expire_all()
result2 = rmod.run_reschedule_pipeline("user_1")
sessions2 = db.query(ScheduledSession).filter_by(status="pending").all()
print(f"[4] Re-scheduled: {result2['status']}, {len(sessions2)} sessions remaining")

# 5. Mark a session failed — triggers reschedule
failed = db.query(ScheduledSession).filter_by(status="pending").first()
if failed:
    failed.status = "failed"
    failed.failed_at = datetime.datetime.utcnow()
    db.commit()
    result3 = rmod.run_reschedule_pipeline("user_1")
    sessions3 = db.query(ScheduledSession).filter_by(status="pending").all()
    print(f"[5] After failure + reschedule: {len(sessions3)} pending sessions")
else:
    print("[5] No sessions to fail — skipped")

# 6. Verify explanation was stored
db.expire_all()
prefs_check = db.query(UserPreferences).filter_by(user_id="user_1").first()
if os.environ.get("GEMINI_API_KEY") and os.environ["GEMINI_API_KEY"] != "test_key":
    assert prefs_check.last_schedule_explanation, "No explanation stored"
    print(f"[6] Explanation stored: {prefs_check.last_schedule_explanation[:100]}...")
else:
    print(f"[6] Explanation (no real API key): {prefs_check.last_schedule_explanation}")

print("\n=== ALL CHECKS PASSED ===")

import os as _os
db.close()
_os.remove("test_e2e.db")
EOF
```

**Pass criteria:**
- [ ] Task created, sessions scheduled
- [ ] Completing a session reduces remaining hours for next run
- [ ] Failed session triggers reschedule with correct remaining hours
- [ ] LLM explanation stored (requires real API key)

---

## Quick Reference

| Step | File | Key test |
|------|------|----------|
| 1 | main.py, db.py | `curl /health` → 200 |
| 2 | models.py | Insert Task + Prefs, no errors |
| 3 | solver/scheduler.py | OPTIMAL result, no overlaps, deadlines respected |
| 4 | scheduling/context_builder.py | remaining_hours = estimated - completed |
| 5 | llm/explainer.py | Returns non-empty string |
| 6 | jobs/reschedule.py | Sessions written, schedule_dirty = False |
| 7 | routes/*.py | REST CRUD works, validation works |
| 8 | alembic | All tables in DB |
| 9 | frontend | `npm run build` succeeds |
| P2-1 | models.py (chat+memory) | Insert ChatMessage + UserMemory |
| P2-2 | llm/tools.py | 6 tools, correct schema |
| P2-3 | llm/tool_executor.py | All 6 tools execute correctly |
| P2-4 | jobs/memory_extractor.py | Extracts + deduplicates memories |
| P2-5 | routes/chat.py | Returns reply, persists messages |
| P2-6 | ChatPanel.jsx | Build passes, UI renders |
| E2E | — | Full task→schedule→complete loop |
