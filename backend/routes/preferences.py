from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import date, datetime

from db import get_db
from models import UserPreferences
from jobs.reschedule import mark_schedule_dirty

router = APIRouter(prefix="/preferences")
HARDCODED_USER_ID = "user_1"

class PrefsUpdate(BaseModel):
    available_days: List[str]
    day_start: str
    day_end: str
    max_sessions_per_day: int = 3
    min_break_minutes: int = 30
    preferred_session_mins: int = 60
    max_session_mins: int = 120

def row_to_dict(row):
    d = {}
    for c in row.__table__.columns:
        val = getattr(row, c.name)
        if isinstance(val, (date, datetime)):
            d[c.name] = val.isoformat()
        else:
            d[c.name] = val
    return d

@router.get("/")
def get_preferences(db: Session = Depends(get_db)):
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == HARDCODED_USER_ID).first()
    if not prefs:
        prefs = UserPreferences(user_id=HARDCODED_USER_ID)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return row_to_dict(prefs)

@router.put("/")
def update_preferences(body: PrefsUpdate, db: Session = Depends(get_db)):
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == HARDCODED_USER_ID).first()
    if not prefs:
        prefs = UserPreferences(user_id=HARDCODED_USER_ID)
        db.add(prefs)
    
    prefs.available_days = ",".join(body.available_days)
    prefs.day_start = body.day_start
    prefs.day_end = body.day_end
    prefs.max_sessions_per_day = body.max_sessions_per_day
    prefs.min_break_minutes = body.min_break_minutes
    prefs.preferred_session_mins = body.preferred_session_mins
    prefs.max_session_mins = body.max_session_mins
    
    db.commit()
    
    return {"ok": True}
