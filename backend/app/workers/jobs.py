import logging
from app.core.database import SessionLocal
from app.services.scheduling_service import run_scheduling_pipeline

logger = logging.getLogger(__name__)

def regenerate_schedule_job():
    """Background job to run the scheduling solver."""
    db = SessionLocal()
    try:
        logger.info("Starting schedule regeneration job")
        num_sessions = run_scheduling_pipeline(db)
        logger.info(f"Schedule regenerated: {num_sessions} sessions created")
    except Exception as e:
        logger.error(f"Schedule regeneration failed: {str(e)}")
    finally:
        db.close()
