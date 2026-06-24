import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.models.memory import UserMemory
from app.services.llm.embedding import get_embedding

def backfill():
    db = SessionLocal()
    try:
        memories = db.query(UserMemory).filter(UserMemory.embedding.is_(None)).all()
        if not memories:
            print("No memories to backfill.")
            return

        print(f"Found {len(memories)} memories without embeddings. Starting backfill...")
        success_count = 0
        for i, memory in enumerate(memories):
            print(f"[{i+1}/{len(memories)}] Generating embedding for memory ID: {memory.id}...")
            embedding = get_embedding(memory.content)
            if embedding:
                memory.embedding = embedding
                success_count += 1
            else:
                print(f"Failed to generate embedding for memory ID: {memory.id}")

        db.commit()
        print(f"Successfully backfilled {success_count}/{len(memories)} memories.")
    except Exception as e:
        db.rollback()
        print(f"Backfill failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
