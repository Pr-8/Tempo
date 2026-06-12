# Tempo Technical Deep Dive: Scheduling & AI

This document provides a deep dive into the two most critical components of Tempo: the **Deterministic Constraint Solver** and the **LLM Explanation Engine**.

## 1. The Scheduling Engine (Google OR-Tools)

Tempo uses the `cp_model` from Google's OR-Tools to solve the "Task Placement Problem". 

### Time Model
Time is discretized into 30-minute intervals (slots). The planning horizon is typically 21 days.

### Hard Constraints (Non-Negotiable)
1.  **No Overlap**: A single 30-minute slot can hold at most one session.
2.  **User Availability**: Sessions can only be scheduled during the user's defined working hours and preferred days (e.g., Mon-Fri, 9 AM - 6 PM).
3.  **Task Deadlines**: Every session for a task must be completed before the task's `deadline`.
4.  **Current Time**: No sessions can be scheduled in the past.

### Advanced Features (Current in `backend/solver/scheduler.py`)
*   **Fixed Events**: Support for "Fixed Tasks" (e.g., a lecture or a doctor's appointment) which occupy specific time slots and cannot be moved by the solver.
*   **Soft Constraints (Optimization)**:
    *   **Priority Weighting**: High-priority tasks are incentivized to be scheduled earlier.
    *   **Weekend Penalties**: The solver heavily penalizes scheduling on non-preferred days (weekends) but will do so if it's the only way to meet a deadline.
    *   **Sessions Per Day**: A soft limit on how many sessions are scheduled per day to prevent burnout.

## 2. The AI Engine (Gemini)

Tempo uses Gemini-2.0-flash to provide a "narrative layer" over the deterministic schedule.

### Role of the LLM
The LLM does **NOT** decide the schedule. It reads the output of the solver and explains it to the user. This ensures the schedule is always logically sound and inspectable, while still feeling "smart" and conversational.

### The Explanation Prompt
The system prompt (`backend/app/services/llm/prompts.py`) instructs Gemini to:
*   Be concise and supportive.
*   Explain the reasoning behind task prioritization.
*   Flag potential deadline risks (e.g., "Calculus is due tomorrow, so I've packed your evening").
*   Detail what changed since the last rescheduling event.

## 3. Data Flow: The "Regeneration Loop"

1.  **Trigger**: User adds a task, edits a deadline, or marks a session as "Failed".
2.  **Dirty Flag**: The system marks the schedule as "dirty".
3.  **Job Queue**: A background worker (`backend/app/workers/jobs.py`) picks up the task.
4.  **Solver Pass**:
    *   Future `scheduled` sessions are deleted.
    *   The solver runs against the current task set.
    *   New `ScheduledSession` records are written to the DB.
5.  **LLM Pass**: Gemini generates a new explanation string.
6.  **Broadcast**: A WebSocket message (`ws_manager.py`) notifies the frontend to refresh.

## 4. Future: The Memory System (Phase 2)

While currently excluded from Phase 1, the codebase contains foundations for a "Conversational Memory" system:
*   **Memory Extraction**: After each chat message, a background LLM call extracts facts (e.g., "I have soccer on Tuesdays") and stores them in a `UserMemory` table.
*   **Context Injection**: These facts are injected into future LLM prompts, making the "Coach" feel persistent and personalized.
