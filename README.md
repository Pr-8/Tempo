# Tempo

Tempo is an AI powered schedule planning application. It combines a **deterministic constraint solver (Google OR-Tools)** with an **LLM (Google Gemini)** to help students and busy professionals manage their workloads dynamically. 

---

## Architecture & Features

Tempo uses an LLM to parse user queries, which is sent to a constraint solver that creates the schedule which is explained using another LLM call.

1. **Deterministic Constraint Solver (Google OR-Tools)**: Takes availability preferences, task durations, deadlines, and fixed commitments to generate mathematically optimal study sessions.
2. **Background Regeneration Pipeline (Redis + RQ)**: When a schedule needs recalculating, a single-threaded background worker processes the constraint solver pipeline asynchronously to prevent API request blocking.
3. **AI Coach & Conversations (Google Gemini)**: Translates raw solver output into friendly, actionable schedule explanations. You can chat with "Tempo AI" in real time to add new tasks, query your day, or ask why the solver scheduled tasks in a certain order.
4. **Real-time Updates (WebSockets)**: Syncs background solver updates to the frontend instantaneously.

### Core Domain Model: Tasks vs. Events

*   **Events (Fixed)**: Concrete time blocks with a specific start and end time (e.g., lectures, exams, meetings). The scheduler **cannot** move these and treats these blocks as unavailable.
*   **Tasks (Flexible)**: Flexible study/work items with an estimated duration, deadline, and priority. The scheduler places sessions for these tasks dynamically within your available hours. If a session is missed, it is automatically rescheduled.

---

## Technology Stack

*   **Backend**: FastAPI (Python), PostgreSQL, SQLAlchemy ORM, Alembic migrations, Redis + RQ (Redis Queue), Google OR-Tools, Google Gemini SDK.
*   **Frontend**: React (Vite), FullCalendar (Vite plugin), Axios, Custom HSL dark-mode CSS design system (Vanilla CSS).
*   **Deployment/Services**: Docker Compose.

---

## Prerequisites

Ensure you have the following installed on your system:
*   [Docker](https://www.docker.com/) and Docker Compose
*   [Python 3.10+](https://www.python.org/)
*   [Node.js (v18+)](https://nodejs.org/) & npm

---

## Setup & Installation

### 1. Start Infrastructure Services (PostgreSQL & Redis)
In the root directory, launch the database and background queue services via Docker:
```bash
docker-compose up -d
```
This starts:
*   **PostgreSQL** on port `5432`
*   **Redis** on port `6379`

### 2. Backend Setup
Navigate to the `backend/` directory:
```bash
cd backend
```

1.  **Create a Virtual Environment & Activate It**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**:
    Copy the sample environment file:
    ```bash
    cp .env.example .env
    ```
    Open the newly created `.env` and fill in the values:
    ```env
    DATABASE_URL=postgresql://tempo_user:tempo_password@localhost:5432/tempo_db
    REDIS_URL=redis://localhost:6379
    GEMINI_API_KEY=your_gemini_api_key_here
    ```

4.  **Run Database Migrations**:
    Apply the database schema using Alembic:
    ```bash
    alembic upgrade head
    ```

### 3. Frontend Setup
Navigate to the `frontend/` directory and install the packages:
```bash
cd ../frontend
npm install
```

---

## Running the Application

You can launch the entire stack using either the provided automated script or by starting the services manually.

### Option A: Automated Startup (Recommended)
From the project root directory, run the `launch.sh` bash script. It cleans up any old instances, starts the services in the background, and forwards logs:
```bash
./launch.sh
```
*   **Frontend**: http://localhost:5173
*   **Backend Docs**: http://localhost:8000/docs
*   **Logs**: Check the `logs/` directory in the root (`backend.log`, `worker.log`, `frontend.log`).

To stop all background processes, run:
```bash
pkill -f "uvicorn|run_worker|vite"
```

### Option B: Manual Startup
If you prefer running services in separate terminal windows (make sure your backend `.venv` is activated):

1.  **FastAPI Application Server**:
    ```bash
    cd backend
    uvicorn app.main:app --reload --port 8000
    ```
2.  **Background RQ Worker**:
    ```bash
    cd backend
    python run_worker.py
    ```
3.  **Vite Frontend Server**:
    ```bash
    cd frontend
    npm run dev
    ```

---

## Testing & Seeding

### Seeding Dummy Tasks
To populate the calendar with a set of test tasks and fixed events, run the seed script from the root directory after launching the application:
```bash
./seed_tasks.sh
```

### Database Reset
To clear all data and start with a fresh database setup, run:
```bash
cd backend
python reset_db.py
```

### Running Backend Tests
To run unit and integration tests for the constraint solver and scheduler logic:
```bash
cd backend
pytest
```
