from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from routes import tasks, sessions, preferences
from db import engine
from models import Base

load_dotenv()

# Create database tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tempo API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Register routers
app.include_router(tasks.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
