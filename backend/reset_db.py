from db import SessionLocal
from models import Task, ScheduledSession, ChatMessage, UserMemory, UserPreferences

def reset_database():
    print("--- Resetting Database for New Architecture ---")
    db = SessionLocal()
    
    try:
        # Delete all dynamic data
        db.query(ScheduledSession).delete()
        db.query(ChatMessage).delete()
        db.query(UserMemory).delete()
        db.query(Task).delete()
        
        # Reset Preferences but keep the user
        prefs = db.query(UserPreferences).filter_by(user_id="user_1").first()
        if prefs:
            prefs.last_schedule_explanation = None
            prefs.blocked_dates = ""
        
        db.commit()
        print("✅ SUCCESS: Database cleared. You are ready for a clean test.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_database()
