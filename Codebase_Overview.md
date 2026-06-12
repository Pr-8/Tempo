# Tempo Codebase Overview

This document provides a technical overview of the Tempo codebase, explaining its architecture, domain concepts, and directory structure.

---

## 🏗️ Architecture Overview

Tempo is a modular web application designed around a clean, separation-of-concerns architecture. It separates deterministic scheduling from conversational AI interface:

*   **API & Lifespan**: Built with **FastAPI**. App state starts and manages a background Redis event loop during its lifespan to broadcast real-time events.
*   **Database**: Uses **PostgreSQL** with **SQLAlchemy ORM** for persistent storage, and **Alembic** to manage database schema updates.
*   **Constraint Solver**: An advanced scheduler implemented using **Google OR-Tools** that respects user availability slots, priority tiers, sleep windows, and fixed events.
*   **Asynchronous Jobs**: Background tasks (such as schedule recalculation and Gemini AI explanations) are managed via **Redis** and **RQ (Redis Queue)** workers.
*   **Real-time Synchronization**: Frontend calendar view syncs automatically on background updates using **WebSockets**.

---

## 📂 Project Directory Structure

The project has been fully cleaned up and consolidated. All legacy backend code was migrated into a single modular structure under `backend/app/`.

### 🐍 Backend (`backend/`)

*   `app/main.py`: Entry point for the FastAPI application. Sets up CORS, lifespan handlers, registers API routers, and defines the `/ws` WebSocket endpoint.
*   `app/core/`: Root system utilities:
    *   `db.py`: PostgreSQL connection pooling and session management.
    *   `config.py`: Global environment settings.
    *   `ws_manager.py`: Connection tracking and Redis pub/sub broadcasting for WebSockets.
*   `app/api/routes/`: REST API controllers grouped by feature:
    *   `tasks.py`: CRUD endpoints for flexible tasks and fixed events.
    *   `sessions.py`: Tracking endpoints to mark study sessions as completed or failed.
    *   `preferences.py`: Read/Write user availability constraints.
    *   `schedule.py`: Triggers schedule optimization.
    *   `chat.py`: Feeds user prompt and session context to the conversational scheduler agent.
*   `app/models/`: SQLAlchemy database models representing tasks, preferences, sessions, chat history, and memory.
*   `app/schemas/`: Pydantic data schemas for request payloads, response serialization, and solver inputs.
*   `app/services/`: Core logic:
    *   `solver/`:
        *   `scheduler.py`: Converts task models to Google OR-Tools constraints (availability intervals, duration matching, non-overlap rules, fixed event constraints).
        *   `models.py`: Intermediate data structures for the scheduler.
        *   `utils.py`: Datetime adjustments and window intersection helpers.
    *   `llm/`:
        *   `gemini.py`: Client wrapper configuring Gemini 2.0 API with timeouts and options.
        *   `tool_executor.py` / `tools.py`: Connects conversational prompts to schedule operations.
        *   `memory_extractor.py`: Auto-extracts preferences from chat history.
*   `app/workers/`: Asynchronous jobs for schedule regeneration and conversational coach logging.
*   `requirements.txt`: Python dependencies.
*   `run_worker.py`: Background RQ worker startup script.
*   `tests/`: Unit and integration test suites.

### ⚛️ Frontend (`frontend/`)

*   `src/App.jsx`: Main interface wrapper. Manages tasks/events listings, theme bindings, WebSocket state, and panels alignment.
*   `src/App.css`: Core design system using modern dark mode tokens, typography (Inter), and layout alignment rules.
*   `src/components/`:
    *   `AddTaskForm.jsx`: A form to add tasks (with flexible durations) and events (with split Date and Time picker fields side-by-side).
    *   `ChatPanel.jsx`: Sleek, scrollable conversational chat with a lightweight inline markdown parser (supporting bold, italic, and bulleted lists).
    *   `ScheduleView.jsx`: Weekly and daily timegrids showing scheduled study sessions (represented by dark glassmorphic pill actions for "Done"/"Failed" states).

---

## 📅 Core Domain Model: Tasks vs. Events

The system handles time allocations in two distinct ways:

1.  **Events (Fixed)**: Specific times (e.g., *Lectures, Jobs, Doctor appointments*). The scheduler cannot move these and marks those calendar intervals as busy. They are automatically marked completed when their scheduled end time passes.
2.  **Tasks (Flexible)**: Flexible study blocks (e.g., *Study Linear Algebra for 3 hours before next Friday*). The scheduler decides when to place study sessions for these items. If a scheduled task session is in the past and has not been marked as `completed` by the user, the scheduler assumes it was missed and automatically schedules a replacement block in the next available slot.