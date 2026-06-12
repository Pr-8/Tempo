from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.preferences import UserPreferences as PreferencesModel
from app.schemas.preferences import UserPreferences, UserPreferencesUpdate

from app.workers.queue import enqueue_regeneration

router = APIRouter(prefix="/preferences", tags=["preferences"])

@router.get("/", response_model=UserPreferences)
def read_preferences(db: Session = Depends(get_db)):
    prefs = db.query(PreferencesModel).first()
    if not prefs:
        # Initialize with defaults if empty for single-user MVP
        now = datetime.now()
        prefs = PreferencesModel(
            id=1,
            available_start_hour=9,
            available_end_hour=17,
            available_days=[0, 1, 2, 3, 4], # Mon-Fri
            min_session_minutes=30,
            max_session_minutes=120,
            max_sessions_per_day=4,
            min_break_minutes=15,
            planning_horizon_days=21,
            updated_at=now
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs

@router.put("/", response_model=UserPreferences)
def update_preferences(prefs_in: UserPreferencesUpdate, db: Session = Depends(get_db)):
    db_prefs = db.query(PreferencesModel).first()
    if not db_prefs:
        db_prefs = PreferencesModel(id=1)
        db.add(db_prefs)
    
    update_data = prefs_in.model_dump()
    for field, value in update_data.items():
        setattr(db_prefs, field, value)
    
    db_prefs.updated_at = datetime.now()
    db.commit()
    db.refresh(db_prefs)
    enqueue_regeneration()
    return db_prefs
