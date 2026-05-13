# Tempo — Project Idea & Vision
---

## The Core Idea

Tempo is a hybrid AI academic task scheduling system. The LLM layer handles language — understanding what the user tells it, explaining what the system has decided, and managing conversation. A constraint solver (Google OR-Tools) handles the actual scheduling — placing tasks into time slots in a way that is provably optimal and consistent given the user's constraints. The two components communicate through a well-defined structured format and never substitute for each other's role.

The result: a system that feels intelligent and conversational on the surface, but produces schedules that are mathematically correct and trustworthy underneath.

The central loop the product is built around:

```
Tell the system what you need to do
        ↓
Get a schedule that fits your life
        ↓
Mark things done or failed as you go
        ↓
Schedule automatically adapts
        ↓
Repeat until exams are over
```

Everything else — analytics, integrations, memory, risk scoring — exists to make this loop more accurate, more personalised, and more useful over time.

---

## Architecture Overview

### The Two-Engine Design

The system has two distinct computational engines with different responsibilities:

**LLM Engine (Gemini)**
- Understands natural language input
- Extracts structured task data from syllabi, emails, and conversation
- Modifies the constraint set in response to user instructions
- Explains scheduling decisions in plain English
- Manages the conversational interface
- Detects patterns in user behaviour and surfaces insights

**Constraint Solver (OR-Tools CP-SAT)**
- Places tasks into time slots
- Enforces all scheduling constraints (working hours, breaks, deadlines, session length)
- Optimises for configurable goals (minimise deadline risk, distribute load evenly, respect preferences)
- Handles infeasibility detection and reporting
- Runs in seconds even for complex semester-length schedules

These engines never directly interact. Between them sits a well-defined JSON contract — the Scheduling Request — which the LLM produces and the solver consumes. This separation means either engine can be swapped, upgraded, or tuned independently.

### The Task Store

Every task in the system — regardless of how it was created — lives in a single normalised database table. This is the central source of truth. The solver reads from it. The chat interface writes to it. Every entry mode writes to it. No component bypasses it.

```
Task {
  id, title, course, estimated_hours, deadline,
  priority, status, source, created_at, last_scheduled_at
}
```

Status lifecycle: `pending → in_progress → complete | failed`

Failed tasks re-enter the scheduling pipeline automatically. Their remaining hours (original estimate minus completed session time) are fed back to the solver, which finds new slots.

### The Pipeline

Every scheduling run follows the same pipeline, regardless of what triggered it:

```
Trigger (new task / edit / failed session / manual request)
        ↓
Context Builder
(assembles: all pending tasks, user constraints, preferences, memory)
        ↓
LLM Call #1 — Parser / Constraint Editor
(produces: Scheduling Request JSON)
        ↓
OR-Tools Solver
(produces: Solver Output JSON — sessions assigned to slots)
        ↓
LLM Call #2 — Explainer
(produces: plain-English summary of schedule and tradeoffs)
        ↓
DB write + calendar sync + user notification
```

This pipeline runs as a background job (queued via Redis/BullMQ). A dirty flag on the user's schedule record debounces rapid consecutive changes into a single solver run.

---

## Data Entry Pipeline

Tasks can enter the Task Store from multiple independent sources. Each source has its own normalisation path but they all converge on the same schema and validation step. No source writes directly without passing through deduplication and validation.

### Entry Modes

**Manual Form**
The baseline. User enters title, course, estimated hours, deadline, and priority directly. No LLM involved. Always available as a fallback and for users who prefer explicit control.

**Natural Language via Chat**
User describes a task conversationally. A lightweight LLM extraction call parses the message and returns structured JSON with confidence scores per field. High-confidence fields are accepted; low-confidence fields trigger a targeted clarification question before writing. Relative dates ("next Friday", "before Easter") are resolved to absolute dates using the current date in the system prompt.

**Syllabus Upload (PDF / text)**
User uploads a course document. Text is extracted (PyMuPDF for PDFs), then passed to an LLM batch extraction call that identifies all assessable tasks, exams, and deadlines. Output is shown to the user in a review screen — they confirm, edit estimated hours, and discard irrelevant items before anything is written. Human review is mandatory here because syllabi are noisy.

**Moodle / LMS Integration**
Connects to Moodle, Canvas, or Blackboard via OAuth and their REST APIs. Pulls assignments and deadlines as already-structured data — no LLM extraction needed. Runs periodically and surfaces new items as notifications for user confirmation. Deadline changes on existing tasks are flagged rather than applied silently.

**Email Parsing**
Monitors the user's inbox (Gmail / Outlook, with permission) for academic task announcements. A binary LLM classification pass first determines whether an email contains a new task or deadline. Only emails that pass are sent to the full extraction call. All candidates are surfaced as notifications — nothing is written to the Task Store without user confirmation.

**Calendar Import**
User imports an `.ics` file or connects a calendar. Events are parsed and classified: deadline-like events (title contains "exam", "due", "submit") become task candidates; all other events are treated as blocked time constraints fed into the solver's constraint set.

### Deduplication

Every write to the Task Store passes through a fuzzy deduplication check on (title, course, deadline). Matches above a similarity threshold are surfaced to the user as a merge prompt rather than written as duplicates. This handles the common case where a task appears in the syllabus, Moodle, and a chat message all within the same week.

---

## Memory System

The LLM has no persistent memory between API calls. Memory is a backend system that assembles relevant context and injects it into every prompt. Three distinct types:

**Structured Preferences**
Collected at onboarding and editable via settings. Always injected. Covers: working hours, available days, max sessions per day, preferred session length, minimum break duration, preferred time of day for hard tasks. When the user updates a preference via chat ("I work better in the evenings now"), an LLM extraction call detects the change and writes it to the preferences table.

**Extracted Conversational Facts**
After each chat message, a background LLM call extracts any new persistent facts — constraints, personal context, stated struggles. These are stored in a `UserMemory` table and retrieved via semantic vector search (pgvector) before each relevant LLM call. Only facts semantically relevant to the current query are injected, keeping prompts focused. A deduplication step resolves contradictions before writing. Facts carry a `last_referenced_at` timestamp and decay out of regular injection when stale.

**Performance Data**
Not stored as text memories. Computed fresh from database aggregates at query time and injected as a plain-English summary. Example: *"Calculus: 58% average score, 70% task completion rate — struggling. Physics: 74% average score, 90% completion rate — on track."* This means performance context is always current without requiring any memory management.

---

## Features

### Core (MVP)

**Automated Schedule Generation**
Given a list of tasks with deadlines and a set of user constraints, the solver produces an optimal schedule across a configurable planning horizon (default 21 days). Sessions are sized according to task complexity and user preferences. The schedule is explained in plain English by the LLM, including priority reasoning and any tradeoffs or warnings.

**Task Entry (Manual)**
Form-based task creation with: title, course, estimated hours, deadline, priority. Immediately triggers a schedule re-run.

**User Constraints**
Onboarding form captures: available days and hours, max sessions per day, min break between sessions, preferred and maximum session length. These are the hard constraints the solver never violates.

**Schedule View**
Week-view calendar displaying all scheduled sessions. Each card shows task, course, time, duration, and priority. Navigation to future weeks. LLM summary at the top.

**Mark Complete / Mark Failed**
Primary daily interactions. Complete closes the session. Failed triggers an automatic reschedule — the solver re-runs and new sessions are found for the remaining hours. User is notified of what moved.

### Full Version

**Chat Interface**
Conversational interface backed by Claude tool use. Tools available to the LLM: `add_task`, `move_session`, `block_time`, `get_schedule`, `update_preference`. Every tool call is logged. After any schedule-modifying tool call, the solver re-runs and the LLM explains what changed. The user can undo recent changes.

**Syllabus Parser**
PDF/text upload with LLM batch extraction and a human review screen before committing tasks.

**LMS Integration**
OAuth connection to Moodle/Canvas. Periodic sync with notification-based confirmation for new items.

**Email Parsing**
Background inbox monitoring with binary classification and user-confirmed task creation.

**Score & Performance Tracking**
User logs test scores and assignment grades. Stored in `PerformanceLog`. Aggregated into per-course summaries injected into scheduling context. Poor performance in a subject automatically increases that subject's task priority weight in the solver.

**Time Tracking**
Records actual start and end times for sessions. Builds a per-user estimate correction model over time — if a user consistently takes longer than estimated on certain task types, the parser step automatically inflates future estimates for those types. Shown to users as a transparency feature ("Based on your history, I've estimated 3.5 hours rather than 2 for this problem set").

**Burnout Detection**
A daily background job computes failure rate, consecutive missed sessions, and scheduled vs completed hours over a rolling 7-day window. If thresholds are exceeded, an LLM call generates a supportive message and injects a temporary load-reduction constraint into the solver (e.g. `max_sessions_per_day: 2` for the coming week). Framed as a suggestion, not an automatic change.

**Risk Scoring**
A weekly background LLM call reads performance summary, upcoming deadlines, remaining task hours, and current completion rate per course. Returns a 0–100 risk score and one-sentence explanation per course. Displayed as a dashboard widget. *"Calculus: 74 — exam in 9 days, 11 hours of prep remaining, and you've been completing about 60% of scheduled sessions. Consider increasing sessions this week."*

**External Calendar Sync**
Two-way sync with Google Calendar and Outlook via OAuth. Scheduled sessions are pushed as calendar events. Blocked times in the user's external calendar are pulled and merged into the solver's constraint set before each run. Conflicts surface as notifications.

---

## Solver Design

The OR-Tools CP-SAT solver discretises time into 30-minute slots across the planning horizon. Tasks are split into sessions (contiguous slot blocks). The solver assigns sessions to slots subject to constraints.

**Hard constraints (always enforced):**
- No session overlaps
- No sessions outside user's available windows
- No sessions on blocked days or times
- All sessions for a task must complete before its deadline
- Session length between configured min and max
- Minimum break duration between any two sessions
- Maximum sessions per day

**Soft constraints (optimised via objective function):**
- Preferred time of day per task type
- No same subject on consecutive days
- Even load distribution across the planning horizon
- Preference for earlier scheduling of high-priority tasks

**Infeasibility handling:** when no valid schedule exists (insufficient time before deadlines), the solver returns a list of tasks it could not place and a per-task explanation of why. The LLM translates this into actionable advice: which deadline is the problem, how much time is missing, and what the user's options are.

**Performance:** typical student workload (10–20 tasks over a 3–4 week horizon) solves in under one second. Semester-length planning (50+ tasks over 16 weeks) solves in under 10 seconds with a time limit configured on the solver.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (web), React Native (mobile — later) |
| Backend | Python / FastAPI |
| Database | PostgreSQL + pgvector |
| Scheduling Engine | Google OR-Tools (CP-SAT) |
| LLM | Gemini 2.0 Flash (free tier)|
| Job Queue | Redis + BullMQ |
| Auth | Supabase Auth |
| PDF Extraction | PyMuPDF |
| Fuzzy Matching | RapidFuzz (deduplication) |
| Calendar APIs | Google Calendar API, Microsoft Graph API |
| LMS APIs | Moodle REST API, Canvas API |

---

## Build Phases

### Phase 1 — MVP (Test the core loop)
Manual task entry → OR-Tools schedule generation → week view → mark complete / mark failed → auto-reschedule → LLM explanation. Single user, no auth. Goal: validate that students trust and follow the generated schedule and engage with the reschedule interaction.

### Phase 2 — Chat & Memory
Chat interface with tool use. Natural language task entry. Structured preferences system. Conversational memory extraction. Goal: validate that the chat interface is a faster and more natural way to interact than forms.

### Phase 3 — Integrations
Syllabus upload and LMS sync (Moodle first). Email parsing. External calendar sync. Goal: reduce manual data entry to near zero for a typical student.

### Phase 4 — Intelligence Layer
Score tracking, time tracking, estimate correction, burnout detection, risk scoring. Goal: the system becomes measurably more accurate and useful the longer a student uses it.



