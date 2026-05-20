# AI Study Planner — Technical Architecture

## Overview

The system is a hybrid AI scheduling application. The LLM handles language understanding, user interaction, and explanation. A constraint solver handles the actual scheduling. They communicate through a well-defined structured format and never directly replace each other's role.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (web), React Native (mobile) |
| Backend | Python / FastAPI |
| Database | PostgreSQL + pgvector extension |
| Scheduling Engine | Google OR-Tools (CP-SAT solver) |
| LLM | Google AI studio |
| Job Queue | Redis + BullMQ |
| Auth | Supabase Auth |
| External Integrations | Google Calendar / Outlook APIs, Moodle REST API |

---

## Core Data Models

### Task
The central unit of the system. Every task — regardless of how it was created — lives in one table.

```
Task {
  id
  title
  course_id              # nullable — not all tasks belong to a course
  estimated_hours
  deadline
  priority               # low | medium | high
  status                 # pending | in_progress | complete | failed
  source                 # syllabus | chat | manual | moodle
  created_at
  last_scheduled_at
}
```

### Other Models
- **User** — preferences, working hours, notification settings
- **ScheduledSession** — a concrete time block assigned to a task (linked to Task)
- **CalendarEvent** — synced record for external calendar providers
- **UserMemory** — extracted persistent facts about the user (see Memory Layer)
- **PerformanceLog** — scores, completion rates, streaks per course
- **ChatThread** — message history and tool calls made via the chat interface

---

## System Architecture

```
User Input (chat / syllabus upload / manual form / Moodle)
         |
         v
   [Task Store]  <---------- single source of truth for all tasks
         |
         v
  Context Builder
  (assembles: tasks, constraints, user preferences, memory)
         |
         v
  LLM Call #1: Parser / Constraint Editor
  (understands natural language, updates constraint set)
         |
         v
  Structured Scheduling Request (JSON)
         |
         v
  OR-Tools Constraint Solver
  (places tasks into time slots, respects all constraints)
         |
         v
  Solver Output (schedule JSON + metadata)
         |
         v
  LLM Call #2: Explainer
  (narrates the schedule, flags tradeoffs, answers questions)
         |
         v
  DB Write + Calendar Sync → User sees schedule
```

---

## Key Components

### 1. Task Store

The Task Store is the central source of truth. It is populated from multiple independent ingestion paths — none of which have any knowledge of each other or of the solver.

**Ingestion paths:**
- **Syllabus Parser** — LLM extraction pass on uploaded PDF/text; outputs structured task records
- **Chat Task Handler** — lightweight LLM call that extracts a single task from a conversational message
- **Manual UI Form** — direct user input, no LLM involved
- **Integration Adapters** — Moodle, Google Classroom, etc. pull deadlines via their APIs

All paths write to the same `tasks` table with the same schema. The solver reads exclusively from this table and is indifferent to where tasks came from.

**Clarification loop:** If a task message is ambiguous (missing duration, unclear deadline), the chat handler returns a clarification question rather than writing an incomplete record. Example: *"You mentioned reviewing notes before the exam — did you mean the Calculus exam on May 18th? And how long do you think you'll need?"*

### 2. Context Builder

Before every LLM call, the backend assembles a context payload from the database and injects it into the system prompt. The LLM has no persistent memory — it reads a snapshot assembled fresh for each call.

```python
def build_context(user_id, query):
    prefs      = db.get_preferences(user_id)
    memories   = vector_search(query, user_id)   # semantically relevant facts
    schedule   = db.get_schedule(user_id, days=14)
    perf       = db.get_performance_summary(user_id)
    return format_as_system_prompt(prefs, memories, schedule, perf)
```

### 3. LLM Call #1 — Parser / Constraint Editor

This call's only job is understanding and translation. It never places tasks.

**On initial schedule generation:** reads raw syllabus or user input, produces a structured Scheduling Request JSON containing the full task list, constraint set, and optimisation goals.

**On chat edits:** reads the existing constraint set plus the user's message, returns a modified constraint set. Example — *"I can't do anything Wednesday"* → adds Wednesday as a blocked day in the constraint object.

**Structured Scheduling Request (the contract between LLM and solver):**
```json
{
  "tasks": [
    {
      "id": "t1",
      "title": "Calculus Chapter 5 Review",
      "estimated_hours": 3.0,
      "deadline": "2026-05-18",
      "priority": "high",
      "preferred_time_of_day": "morning"
    }
  ],
  "constraints": {
    "available_windows": [
      { "days": ["mon","tue","wed","thu","fri"], "start": "09:00", "end": "18:00" }
    ],
    "blocked_times": [],
    "session_rules": {
      "min_session_minutes": 45,
      "max_session_minutes": 120,
      "min_break_between_sessions": 30,
      "max_sessions_per_day": 3
    }
  },
  "optimisation_goals": {
    "primary": "minimise_deadline_risk",
    "secondary": "respect_time_of_day_preferences",
    "tertiary": "distribute_load_evenly"
  }
}
```

### 4. OR-Tools Constraint Solver

Pure Python, no LLM involved. Takes the Scheduling Request and finds the optimal valid assignment of tasks to time slots using the CP-SAT solver.

**Hard constraints (must never be violated):**
- No two sessions overlap
- No sessions outside available windows
- No sessions on blocked days/times
- All sessions for a task must complete before its deadline
- Session length within min/max bounds
- Minimum break between sessions

**Soft constraints (optimised for, penalties for violations):**
- Preferred time of day per task
- No same subject on consecutive days
- Even load distribution across the week

**Infeasibility handling:** if the constraint set has no valid solution (e.g. 40 hours of work, 25 hours available before deadlines), the solver returns an infeasibility report. This gets passed to LLM Call #2 which communicates it clearly to the user with specific suggestions — e.g. which deadline is at risk and by how much.

### 5. LLM Call #2 — Explainer

Receives the solver output and narrates it. Explains priority ordering, flags heavy days, notes any tradeoffs made. This is where the product feels intelligent rather than mechanical.

Example output: *"I've front-loaded your Calculus prep across Monday and Tuesday mornings since the exam is in 7 days — that's your tightest deadline. Physics is spread over next week. One thing to watch: Thursday is quite heavy at 4.5 hours; let me know if you'd like me to shift something."*

### 6. Chat Interface (Tool Use)

The chat interface uses Claude's tool use capability. Tools are defined actions the LLM can trigger in the backend. When a user sends a message, Claude decides whether to call a tool or just reply.

**Available tools:**
- `get_schedule(date_range)` — read current schedule
- `add_task(details)` — write new task to Task Store
- `move_session(session_id, new_time)` — reschedule a specific session
- `block_time(date_range, reason)` — add a constraint
- `update_preference(key, value)` — persist a user preference

Every tool call is logged in `ChatThread.tool_calls[]` so the user can see what changed. After any tool call that modifies the schedule, the solver re-runs and LLM Call #2 reports what moved.

---

## Memory Layer

The LLM has no memory between calls. "Memory" is a backend system that stores information and retrieves it for context injection.

### Three types of memory:

**Structured preferences** — collected at onboarding and via settings UI. Always injected. Example: working hours, max sessions per day, notification preferences.

**Extracted conversational facts** — after each chat message, a background LLM call extracts any new persistent facts and writes them to the `UserMemory` table. Example: *"User has football training every Thursday at 7pm."* Retrieved via semantic vector search (pgvector) — only facts relevant to the current query are injected, keeping prompts focused.

**Performance data** — not stored as text memories. Computed fresh from DB aggregates at query time and formatted as a plain-English summary. Example: *"Calculus: 58% avg score, 70% task completion — struggling. Physics: 74% avg score, 90% completion — on track."*

**Memory hygiene:** a deduplication step checks new extracted facts against existing ones before writing, resolving contradictions (e.g. user previously said mornings, now says evenings). Memories carry a `last_referenced_at` timestamp; stale facts decay out of regular injection.

---

## Rescheduling Triggers

The solver re-runs whenever the schedule becomes stale. A dirty flag on the user's schedule record triggers a background job (debounced — multiple rapid changes produce one solver run).

| Trigger | Action |
|---|---|
| New task added (any source) | Dirty flag → solver re-run |
| Task marked as failed | Dirty flag → solver re-run |
| Chat edit modifies constraints | Dirty flag → solver re-run |
| Deadline passes with task incomplete | Status updated → dirty flag |
| Performance data changes priority weights | Dirty flag → solver re-run |

---

## Optional Features — Integration Points

These plug into the existing pipeline without changing its structure.

**Score tracking (Feature 5):** writes to `PerformanceLog`. A pre-processing step before the solver reads performance data and adjusts `priority` fields on tasks — poor scores in a subject increase priority automatically.

**External calendar sync (Feature 6):** `IntegrationAdapter` interface with implementations for Google Calendar and Outlook. `pushEvent()` and `pullEvents()` methods. Blocked times pulled from external calendars are merged into the constraint set before each solver run.

**Time tracking (Feature 7):** records `actual_start` and `actual_end` on each session. Builds a per-user estimate correction factor (e.g. user takes 40% longer on maths tasks than estimated). Applied as a multiplier on `estimated_hours` in the Parser step before the solver sees the task.

**Burnout detection (Feature 8):** a daily background job computes failure rate and consecutive missed tasks over a rolling 7-day window. If thresholds are exceeded, an LLM call generates a supportive nudge and injects a temporary `max_sessions_per_day: 2` constraint into the next solver run.

**Risk scoring (Feature 9):** a separate weekly LLM call reads performance summary, upcoming deadlines, and remaining hours. Returns a 0–100 risk score and a one-sentence explanation per course. Displayed as a dashboard widget. Does not interact with the scheduling pipeline.