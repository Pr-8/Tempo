from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.services.google_calendar import GoogleCalendarService
from app.models.calendar_event import CalendarEvent
from app.models.google_token import GoogleCalendarToken

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.get("/auth-url")
def get_auth_url(db: Session = Depends(get_db)):
    try:
        gcal = GoogleCalendarService(db)
        url = gcal.get_auth_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback", response_class=HTMLResponse)
def oauth_callback(code: str, db: Session = Depends(get_db)):
    try:
        gcal = GoogleCalendarService(db)
        gcal.exchange_code(code)
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    background-color: #121214;
                    color: #e4e4e7;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }
                .card {
                    background: #1e1e24;
                    padding: 24px 32px;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    text-align: center;
                    border: 1px solid #2d2d34;
                }
                h2 { color: #10b981; margin-top: 0; }
                p { color: #a1a1aa; font-size: 14px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Google Calendar Connected!</h2>
                <p>This window will close automatically.</p>
            </div>
            <script>
                if (window.opener) {
                    window.opener.postMessage("gcal_connected", "*");
                }
                setTimeout(function() {
                    window.close();
                }, 1500);
            </script>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    background-color: #121214;
                    color: #e4e4e7;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }}
                .card {{
                    background: #1e1e24;
                    padding: 24px 32px;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    text-align: center;
                    border: 1px solid #2d2d34;
                }}
                h2 {{ color: #ef4444; margin-top: 0; }}
                p {{ color: #a1a1aa; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Connection Failed</h2>
                <p>{str(e)}</p>
            </div>
            <script>
                if (window.opener) {{
                    window.opener.postMessage("gcal_failed", "*");
                }}
            </script>
        </body>
        </html>
        """

@router.get("/status")
def get_status(user_id: str = "user_1", db: Session = Depends(get_db)):
    token = db.query(GoogleCalendarToken).filter_by(user_id=user_id).first()
    if not token:
        return {"connected": False}
    
    return {
        "connected": True,
        "sync_enabled": token.sync_enabled,
        "last_synced_at": token.last_synced_at.isoformat() if token.last_synced_at else None,
        "calendar_id": token.calendar_id
    }

@router.post("/sync")
def sync_calendar(user_id: str = "user_1", db: Session = Depends(get_db)):
    gcal = GoogleCalendarService(db)
    try:
        events = gcal.pull_events(user_id)
        token = db.query(GoogleCalendarToken).filter_by(user_id=user_id).first()
        if token:
            token.last_synced_at = datetime.now()
            db.commit()
        return {"status": "success", "synced_events": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disconnect")
def disconnect_calendar(user_id: str = "user_1", db: Session = Depends(get_db)):
    gcal = GoogleCalendarService(db)
    try:
        gcal.disconnect(user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events")
def get_events(start: datetime, end: datetime, user_id: str = "user_1", db: Session = Depends(get_db)):
    events = db.query(CalendarEvent).filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_time >= start,
        CalendarEvent.start_time <= end
    ).all()
    
    return [
        {
            "id": str(e.id),
            "google_event_id": e.google_event_id,
            "summary": e.summary,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "is_all_day": e.is_all_day,
            "source": e.source,
            "tempo_session_id": str(e.tempo_session_id) if e.tempo_session_id else None
        }
        for e in events
    ]
