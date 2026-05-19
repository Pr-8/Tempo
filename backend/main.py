from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="Tempo API")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
