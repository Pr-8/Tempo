from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import tasks, preferences, schedule, sessions, chat

app = FastAPI(title="Tempo API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with /api prefix to match frontend expectations
app.include_router(tasks.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}
