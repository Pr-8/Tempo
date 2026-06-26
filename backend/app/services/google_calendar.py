import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.core.config import settings
from app.models.google_token import GoogleCalendarToken
from app.models.calendar_event import CalendarEvent
from app.models.session import Session as SessionModel
from app.models.task import Task as TaskModel

class GoogleCalendarService:
    def __init__(self, db: Session):
        self.db = db

    def _get_client_config(self) -> Dict[str, Any]:
        return {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }

    def get_auth_url(self) -> str:
        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            autogenerate_code_verifier=False
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return authorization_url

    def exchange_code(self, code: str, user_id: str = "user_1") -> GoogleCalendarToken:
        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            autogenerate_code_verifier=False
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)
        credentials = flow.credentials

        db_token = self.db.query(GoogleCalendarToken).filter_by(user_id=user_id).first()
        now = datetime.now()
        
        if db_token:
            db_token.access_token = credentials.token
            if credentials.refresh_token:
                db_token.refresh_token = credentials.refresh_token
            db_token.token_expiry = credentials.expiry.replace(tzinfo=None)
            db_token.scopes = ",".join(credentials.scopes)
            db_token.updated_at = now
        else:
            db_token = GoogleCalendarToken(
                user_id=user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=credentials.expiry.replace(tzinfo=None),
                scopes=",".join(credentials.scopes),
                created_at=now,
                updated_at=now
            )
            self.db.add(db_token)
        
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_credentials(self, user_id: str = "user_1") -> Optional[Credentials]:
        db_token = self.db.query(GoogleCalendarToken).filter_by(user_id=user_id).first()
        if not db_token:
            return None

        # Convert local naive token_expiry back to naive UTC for google libraries
        expiry_utc = db_token.token_expiry
        
        creds = Credentials(
            token=db_token.access_token,
            refresh_token=db_token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=db_token.scopes.split(",")
        )
        # Manually assign expiry so expired check works
        creds.expiry = expiry_utc

        if creds.expired:
            try:
                creds.refresh(Request())
                db_token.access_token = creds.token
                if creds.refresh_token:
                    db_token.refresh_token = creds.refresh_token
                db_token.token_expiry = creds.expiry.replace(tzinfo=None)
                db_token.updated_at = datetime.now()
                self.db.commit()
            except Exception as e:
                print(f"Error refreshing Google OAuth credentials: {e}")
                return None

        return creds

    def pull_events(self, user_id: str = "user_1", time_min: Optional[datetime] = None, time_max: Optional[datetime] = None) -> List[CalendarEvent]:
        creds = self.get_credentials(user_id)
        if not creds:
            return []

        if not time_min:
            time_min = datetime.now()
        if not time_max:
            time_max = time_min + timedelta(days=settings.PLANNING_HORIZON_DAYS)

        service = build('calendar', 'v3', credentials=creds)

        # Build aware local times to convert to UTC for the request parameters
        local_tz = datetime.now().astimezone().tzinfo
        time_min_aware = time_min.replace(tzinfo=local_tz)
        time_max_aware = time_max.replace(tzinfo=local_tz)

        events_result = service.events().list(
            calendarId=settings.GOOGLE_REDIRECT_URI if False else 'primary',  # Just primary
            timeMin=time_min_aware.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
            timeMax=time_max_aware.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        
        # Clear existing cached google events in this range
        self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.source == "google",
            CalendarEvent.start_time >= time_min,
            CalendarEvent.start_time < time_max
        ).delete()

        pulled_events = []
        now = datetime.now()
        for e in events:
            if 'date' in e['start']:
                # Skip all day events
                continue

            start_str = e['start'].get('dateTime')
            end_str = e['end'].get('dateTime')
            if not start_str or not end_str:
                continue

            # Convert timezone aware string to system local naive datetime
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')).astimezone().replace(tzinfo=None)

            # Check if this is a Tempo-scheduled event
            is_tempo = False
            if 'extendedProperties' in e and 'private' in e['extendedProperties']:
                if e['extendedProperties']['private'].get('source') == 'tempo':
                    is_tempo = True
            elif e.get('description') and "Scheduled by Tempo" in e.get('description'):
                is_tempo = True

            if is_tempo:
                continue

            db_event = CalendarEvent(
                user_id=user_id,
                google_event_id=e['id'],
                summary=e.get('summary', 'No Title'),
                start_time=start_dt,
                end_time=end_dt,
                is_all_day=False,
                source="google",
                synced_at=now
            )
            self.db.add(db_event)
            pulled_events.append(db_event)

        self.db.commit()
        return pulled_events

    def push_sessions(self, user_id: str, sessions: List[SessionModel], tasks: Dict[UUID, TaskModel]) -> int:
        creds = self.get_credentials(user_id)
        if not creds:
            return 0

        service = build('calendar', 'v3', credentials=creds)

        # Get existing cache of tempo events
        existing_events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.source == "tempo"
        ).all()

        existing_event_map = {e.tempo_session_id: e for e in existing_events}
        active_session_ids = {s.id for s in sessions}

        # Delete calendar events on Google Calendar for sessions that were deleted or rescheduled
        for sess_id, cached_event in list(existing_event_map.items()):
            if sess_id not in active_session_ids:
                try:
                    service.events().delete(
                        calendarId='primary',
                        eventId=cached_event.google_event_id
                    ).execute()
                except Exception:
                    pass
                self.db.delete(cached_event)
                del existing_event_map[sess_id]
        self.db.commit()

        pushed_count = 0
        local_tz = datetime.now().astimezone().tzinfo
        now = datetime.now()

        for s in sessions:
            task = tasks.get(s.task_id)
            if not task:
                continue

            summary = f"Study: {task.title}"
            description = f"Scheduled by Tempo\nCourse: {task.course}\nDuration: {s.duration_minutes} minutes"
            
            start_aware = s.start_time.replace(tzinfo=local_tz)
            end_aware = s.end_time.replace(tzinfo=local_tz)

            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_aware.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                },
                'end': {
                    'dateTime': end_aware.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                },
                'colorId': '3',  # Grape color
                'extendedProperties': {
                    'private': {
                        'source': 'tempo',
                        'session_id': str(s.id),
                        'task_id': str(task.id)
                    }
                }
            }

            cached_event = existing_event_map.get(s.id)
            if cached_event:
                try:
                    service.events().update(
                        calendarId='primary',
                        eventId=cached_event.google_event_id,
                        body=event_body
                    ).execute()
                    cached_event.summary = summary
                    cached_event.start_time = s.start_time
                    cached_event.end_time = s.end_time
                    cached_event.synced_at = now
                    pushed_count += 1
                except Exception:
                    # Recreate if update failed (e.g. deleted manually on google calendar)
                    cached_event = None

            if not cached_event:
                try:
                    g_event = service.events().insert(
                        calendarId='primary',
                        body=event_body
                    ).execute()

                    new_cache = CalendarEvent(
                        user_id=user_id,
                        google_event_id=g_event['id'],
                        summary=summary,
                        start_time=s.start_time,
                        end_time=s.end_time,
                        is_all_day=False,
                        source="tempo",
                        tempo_session_id=s.id,
                        synced_at=now
                    )
                    self.db.add(new_cache)
                    pushed_count += 1
                except Exception as e:
                    print(f"Error pushing Google Calendar event: {e}")

        self.db.commit()
        return pushed_count

    def delete_pushed_events(self, user_id: str) -> int:
        creds = self.get_credentials(user_id)
        if not creds:
            return 0

        service = build('calendar', 'v3', credentials=creds)
        
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.source == "tempo"
        ).all()

        deleted_count = 0
        for e in events:
            try:
                service.events().delete(
                    calendarId='primary',
                    eventId=e.google_event_id
                ).execute()
                deleted_count += 1
            except Exception:
                pass
            self.db.delete(e)
            
        self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.source == "google"
        ).delete()
        
        self.db.commit()
        return deleted_count

    def disconnect(self, user_id: str = "user_1"):
        self.delete_pushed_events(user_id)
        
        db_token = self.db.query(GoogleCalendarToken).filter_by(user_id=user_id).first()
        if db_token:
            self.db.delete(db_token)
            self.db.commit()
