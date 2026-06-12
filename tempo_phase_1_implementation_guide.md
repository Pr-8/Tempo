# Tempo — Phase 1 Implementation Guide

Source project specification: fileciteturn0file0L1-L999

---

# Purpose of This Document

This document is written for an AI coding agent that will implement Phase 1 of Tempo.

The goal is to provide:

- Exact implementation boundaries
- Folder structure
- Database schema
- API contracts
- Solver architecture
- State flow
- Scheduling logic
- Development sequence
- Non-goals
- Acceptance criteria

This guide intentionally avoids ambiguity.

Phase 1 should produce a fully working local MVP with:

1. Manual task entry
2. OR-Tools schedule generation
3. Calendar/week view
4. Mark complete / mark failed
5. Automatic rescheduling
6. LLM-generated schedule explanations
7. Single-user local deployment

No auth.
No integrations.
No memory system.
No chat.
No background intelligence.

---

# Phase 1 Scope

## Features INCLUDED

### Core Scheduling
- Manual task CRUD
- Constraint configuration
- Schedule generation
- Auto-rescheduling
- Week calendar UI
- Schedule explanations
- Completion/failure tracking

### Backend
- FastAPI backend
- PostgreSQL database
- OR-Tools CP-SAT solver
- Redis + RQ jobs
- Gemini API integration
- REST APIs

### Frontend
- React web app
- Task creation form
- Constraints settings form
- Weekly calendar view
- Session cards
- Complete/Fail interactions
- Solver status display
- Explanation display

---

## Features EXCLUDED

Do NOT implement:

- Authentication
- Multi-user support
- Chat interface
- Memory system
- LMS integrations
- Email parsing
- Calendar sync
- PDF parsing
- Syllabus extraction
- Performance analytics
- Burnout detection
- Risk scoring
- Notifications
- Mobile app
- Real-time collaboration
- AI tool use
- Vector search
- Preference extraction from conversation

---

# Technical Architecture

## High-Level Architecture

```text
Frontend (React)
    ↓ REST
Backend API (FastAPI)
    ↓
PostgreSQL
    ↓
Redis Queue
    ↓
Worker
    ↓
OR-Tools Solver
    ↓
Gemini Explainer
    ↓
Database Update
```

---

# Recommended Repository Structure

```text
tempo/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── dependencies/
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── logging.py
│   │   │
│   │   ├── models/
│   │   │   ├── task.py
│   │   │   ├── session.py
│   │   │   ├── preferences.py
│   │   │   └── schedule.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── task.py
│   │   │   ├── session.py
│   │   │   └── preferences.py
│   │   │
│   │   ├── services/
│   │   │   ├── solver/
│   │   │   │   ├── scheduler.py
│   │   │   │   ├── constraints.py
│   │   │   │   ├── objective.py
│   │   │   │   └── models.py
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── gemini.py
│   │   │   │   └── prompts.py
│   │   │   │
│   │   │   ├── scheduling_service.py
│   │   │   └── reschedule_service.py
│   │   │
│   │   ├── workers/
│   │   │   ├── queue.py
│   │   │   └── jobs.py
│   │   │
│   │   └── main.py
│   │
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── store/
│   │   ├── types/
│   │   └── utils/
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml
├── README.md
└── .env
```

---

# Core Domain Model

## Important Design Rule

There is exactly ONE source of truth for tasks.

Every scheduling operation reads from the same task table.

The solver NEVER stores independent state.

---

# Database Schema

Use PostgreSQL.

Use SQLAlchemy ORM.

Use Alembic migrations.

---

## Table: tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY,

    title TEXT NOT NULL,
    course TEXT NOT NULL,

    estimated_hours FLOAT NOT NULL,
    remaining_hours FLOAT NOT NULL,

    deadline TIMESTAMP NOT NULL,

    priority INTEGER NOT NULL DEFAULT 3,

    status TEXT NOT NULL DEFAULT 'pending',

    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,

    last_scheduled_at TIMESTAMP
);
```

---

## Task Status Values

Allowed:

```text
pending
in_progress
complete
failed
```

Never use enums initially.

Use string validation in application layer.

---

## Table: sessions

Represents actual scheduled blocks.

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,

    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,

    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,

    duration_minutes INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'scheduled',

    created_at TIMESTAMP NOT NULL
);
```

---

## Session Status Values

```text
scheduled
completed
failed
cancelled
```

---

## Table: user_preferences

Single-row table for Phase 1.

```sql
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY DEFAULT 1,

    available_start_hour INTEGER NOT NULL,
    available_end_hour INTEGER NOT NULL,

    available_days JSONB NOT NULL,

    min_session_minutes INTEGER NOT NULL,
    max_session_minutes INTEGER NOT NULL,

    max_sessions_per_day INTEGER NOT NULL,

    min_break_minutes INTEGER NOT NULL,

    planning_horizon_days INTEGER NOT NULL DEFAULT 21,

    updated_at TIMESTAMP NOT NULL
);
```

---

## Table: schedule_runs

Tracks scheduling attempts.

```sql
CREATE TABLE schedule_runs (
    id UUID PRIMARY KEY,

    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,

    status TEXT NOT NULL,

    explanation TEXT,

    infeasible_reason TEXT
);
```

---

# Backend Architecture

## FastAPI Responsibilities

FastAPI should ONLY:

- Validate requests
- Read/write database
- Trigger jobs
- Return responses

The API layer should NOT contain solver logic.

---

# API Endpoints

## Tasks

### POST /tasks

Create task.

Request:

```json
{
  "title": "Calculus Problem Set",
  "course": "Calculus",
  "estimated_hours": 4,
  "deadline": "2026-06-10T18:00:00",
  "priority": 4
}
```

Response:

```json
{
  "id": "uuid",
  "status": "pending"
}
```

Side effects:

1. Insert task
2. Trigger schedule regeneration job

---

### GET /tasks

Returns all tasks.

---

### PATCH /tasks/{id}

Allows:

- Edit title
- Edit estimate
- Edit deadline
- Edit priority
- Mark complete

After edits:

- Trigger regeneration

---

### DELETE /tasks/{id}

Deletes task.

Deletes associated sessions.

Triggers regeneration.

---

# Sessions

## GET /sessions/week

Query params:

```text
start_date=2026-06-01
```

Returns all sessions for that week.

---

## POST /sessions/{id}/complete

Behavior:

1. Mark session completed
2. Reduce task.remaining_hours
3. If remaining_hours <= 0:
   - Mark task complete
4. Else:
   - Mark task in_progress
5. Trigger regeneration

---

## POST /sessions/{id}/fail

Behavior:

1. Mark session failed
2. Leave remaining_hours unchanged
3. Trigger regeneration

---

# Preferences

## GET /preferences

Returns single preferences row.

---

## PUT /preferences

Updates constraints.

Triggers regeneration.

---

# Schedule

## POST /schedule/regenerate

Manual regeneration endpoint.

Should enqueue background job.

---

## GET /schedule/status

Returns:

```json
{
  "status": "idle",
  "last_run": "timestamp",
  "last_explanation": "string"
}
```

---

# Scheduling Pipeline

Every scheduling run MUST follow this exact flow.

```text
Trigger
    ↓
Collect tasks
    ↓
Collect preferences
    ↓
Build scheduling request
    ↓
Run OR-Tools solver
    ↓
Store generated sessions
    ↓
Generate LLM explanation
    ↓
Store explanation
```

---

# Critical Scheduling Rules

## Before Every Solver Run

Delete ALL future scheduled sessions.

Then regenerate from scratch.

Do NOT attempt incremental patching in Phase 1.

Reason:

- Simpler
- More reliable
- Easier debugging
- Avoids stale constraints

Completed sessions should NEVER be deleted.

Failed sessions remain for analytics/history.

Only delete:

```text
status = scheduled
AND start_time > now()
```

---

# OR-Tools Solver Design

## Time Model

Discretize time into 30-minute slots.

Example:

```text
08:00
08:30
09:00
09:30
...
```

Planning horizon:

```text
today → today + planning_horizon_days
```

---

# Session Splitting Logic

Each task must be split into sessions.

Example:

```text
Task: 5 hours
Session size: 1 hour
→ 5 sessions
```

Use this algorithm:

```python
session_size = clamp(
    estimated_hours / 3,
    min_session_length,
    max_session_length
)
```

Then divide task into equal-sized sessions.

Final session may be smaller.

---

# Hard Constraints

Must ALWAYS be enforced.

## Constraint 1 — No Overlap

A slot may contain at most one session.

---

## Constraint 2 — User Availability

Sessions only inside:

- available days
- available hours

---

## Constraint 3 — Before Deadline

Every session for a task must finish before task deadline.

---

## Constraint 4 — Session Length

Respect:

```text
min_session_minutes
max_session_minutes
```

---

## Constraint 5 — Max Sessions Per Day

Respect:

```text
max_sessions_per_day
```

---

## Constraint 6 — Minimum Break

Ensure gap between sessions.

Example:

```text
session A ends 14:00
minimum break = 30 min
next session earliest = 14:30
```

---

# Objective Function

Phase 1 objective should remain simple.

Optimize for:

1. Earlier scheduling of high priority tasks
2. Even distribution across days

Weighted objective:

```text
maximize:
  priority_weight
  + earlier_slot_bonus
  + distribution_score
```

Do NOT implement advanced heuristics.

---

# Infeasibility Handling

If no valid schedule exists:

Return:

```json
{
  "feasible": false,
  "unplaced_tasks": [
    {
      "task_id": "uuid",
      "reason": "insufficient time before deadline"
    }
  ]
}
```

Frontend must display this clearly.

Do NOT silently fail.

---

# Solver Implementation Structure

## scheduler.py

Main orchestration.

Responsibilities:

- Build model
- Add variables
- Add constraints
- Add objective
- Solve
- Transform output

---

## constraints.py

Contains:

- availability constraints
- overlap constraints
- break constraints
- deadline constraints

---

## objective.py

Contains objective scoring only.

Keep isolated.

---

## models.py

Contains:

- scheduling request DTOs
- solver output DTOs

---

# Redis + RQ Jobs

Scheduling should NEVER block API requests.

Use background jobs.

---

# Queue Events

Trigger regeneration after:

- task creation
- task update
- task deletion
- session failure
- session completion
- preference update

---

# Debouncing Requirement

Multiple rapid updates should collapse into ONE solver run.

Implementation:

```text
schedule_dirty = true
```

Worker checks every few seconds.

If dirty:

- clear flag
- run regeneration

Do NOT enqueue unlimited jobs.

---

# Gemini Integration

Phase 1 uses Gemini ONLY for explanations.

NOT for scheduling.

---

# Gemini Input

Input should include:

- pending tasks
- generated sessions
- infeasible tasks
- user preferences

---

# Gemini Prompt

System prompt:

```text
You are explaining an automatically generated study schedule.
Be concise, supportive, and practical.
Explain:
- why tasks were prioritized
- any deadline risks
- how workload was distributed
- what changed after rescheduling
Avoid hallucinating constraints.
```

---

# Gemini Output Example

```text
I scheduled your Calculus work earlier this week because it has the closest deadline and highest priority. Physics sessions were spread across multiple days to avoid overload. Your Friday workload is heavier due to limited availability before the Calculus deadline.
```

Store explanation in database.

---

# Frontend Architecture

Use:

- React
- TypeScript
- Vite
- React Query
- Zustand or Context API
- Tailwind

---

# Required Pages

## Dashboard Page

Contains:

- Week calendar
- Schedule explanation
- Solver status
- Quick actions

---

## Tasks Page

Contains:

- Task table
- Create task modal
- Edit task modal
- Delete action

---

## Preferences Page

Contains:

- Availability settings
- Session settings
- Planning horizon settings

---

# Calendar UI Requirements

Use week view only.

Do NOT implement month view.

Each session card should show:

```text
Task title
Course
Time
Duration
Priority
```

Session card actions:

- Complete
- Fail

---

# Frontend State Rules

Server is source of truth.

Avoid duplicating schedule state locally.

Always re-fetch after mutations.

---

# Error Handling

## Solver Errors

Display:

```text
Unable to generate a valid schedule.
```

Plus infeasibility reasons.

---

## Gemini Errors

Scheduling must STILL succeed.

Explanation generation failure should not block schedule creation.

Fallback message:

```text
Your schedule has been updated.
```

---

# Docker Setup

Use docker-compose.

Services:

```text
frontend
backend
postgres
redis
worker
```

---

# Environment Variables

Backend:

```text
DATABASE_URL=
REDIS_URL=
GEMINI_API_KEY=
```

Frontend:

```text
VITE_API_URL=
```

---

# Development Sequence

The implementation MUST follow this order.

---

# Step 1 — Backend Foundation

Implement:

- FastAPI app
- PostgreSQL connection
- SQLAlchemy models
- Alembic migrations
- Docker setup

Acceptance:

- API starts
- DB migrations run
- Health endpoint works

---

# Step 2 — Task CRUD

Implement:

- Create task
- Read tasks
- Update task
- Delete task

Acceptance:

- CRUD fully functional
- Validation works

---

# Step 3 — Preferences System

Implement:

- Preferences table
- Preferences endpoints
- Validation

Acceptance:

- Constraints editable
- Persist correctly

---

# Step 4 — Basic Solver

Implement:

- Slot generation
- Task splitting
- Constraint solving
- Session persistence

Acceptance:

- Sessions generated correctly
- No overlaps
- Deadlines respected

---

# Step 5 — Regeneration Pipeline

Implement:

- Delete future sessions
- Full regeneration
- Queue worker
- Dirty flag

Acceptance:

- Auto-regeneration works
- No duplicate sessions

---

# Step 6 — Session Actions

Implement:

- Mark complete
- Mark failed
- Remaining hour tracking
- Rescheduling

Acceptance:

- Failed sessions reschedule
- Completed tasks disappear

---

# Step 7 — Gemini Explanations

Implement:

- Gemini client
- Prompt builder
- Explanation persistence

Acceptance:

- Explanations generated
- Failures handled safely

---

# Step 8 — Frontend UI

Implement:

- Dashboard
- Calendar
- Task management
- Preferences
- Session actions

Acceptance:

- Entire flow usable end-to-end

---

# Step 9 — Final Hardening

Implement:

- Validation
- Logging
- Error handling
- Loading states
- Empty states

Acceptance:

- Stable local MVP

---

# Important Engineering Constraints

## Keep Scheduling Deterministic

Given same:

- tasks
- preferences
- current time

The solver should produce same schedule.

Avoid randomness.

---

## Never Let LLM Modify Schedule Directly

LLM is explanatory only.

The solver is the sole authority.

---

## Keep Solver Pure

Solver should:

- take input
- return output

No DB access.

No API calls.

No side effects.

---

## Never Mutate Completed Sessions

Completed sessions are historical records.

Immutable.

---

## Keep Timezone Handling Explicit

Use UTC internally.

Frontend handles local rendering.

---

# Suggested Libraries

## Backend

```text
fastapi
uvicorn
sqlalchemy
alembic
psycopg2-binary
ortools
redis
rq
pydantic
python-dotenv
httpx
```

---

## Frontend

```text
react
typescript
vite
react-query
axios
tailwindcss
zustand
react-big-calendar
date-fns
```

---

# API Contracts

## Schedule Response

```json
{
  "feasible": true,
  "sessions": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "title": "Calculus",
      "start_time": "ISO",
      "end_time": "ISO",
      "duration_minutes": 60,
      "priority": 4
    }
  ],
  "explanation": "string"
}
```

---

# Acceptance Criteria for Phase 1

Phase 1 is COMPLETE only if all conditions below are true.

---

## Functional

- User can create tasks
- Solver generates sessions
- Sessions appear in week calendar
- User can mark session complete
- User can mark session failed
- Failed work is rescheduled automatically
- Schedule explanations appear
- Constraint edits regenerate schedule

---

## Technical

- No overlapping sessions
- No sessions after deadlines
- No sessions outside availability
- Solver runs under 3 seconds for 20 tasks
- API responses under 500ms excluding solver job
- No duplicate sessions after repeated regeneration

---

## UX

- Calendar readable
- Loading states visible
- Errors understandable
- Infeasible schedules explained

---

# Non-Goals for Phase 1

Do NOT optimize prematurely.

Avoid:

- microservices
- event sourcing
- websocket sync
- CQRS
- advanced AI orchestration
- autonomous agents
- plugin systems
- complex caching

The MVP goal is validating:

```text
Do students trust and use automatically generated schedules?
```

Everything else is secondary.

---

# Final Implementation Philosophy

Tempo is fundamentally:

```text
Deterministic scheduling
+
Conversational explanation
```

NOT:

```text
An autonomous AI planner.
```

The scheduling engine must remain:

- deterministic
- inspectable
- debuggable
- constraint-driven

The AI layer exists to improve usability and comprehension — not replace the solver.

