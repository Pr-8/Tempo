from rq import Worker
from app.workers.queue import redis_conn, Queue

if __name__ == "__main__":
    worker = Worker([Queue("tempo_tasks", connection=redis_conn)], connection=redis_conn)
    worker.work()
