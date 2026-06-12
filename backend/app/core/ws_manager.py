from fastapi import WebSocket
from typing import List
import logging
import json
from app.core.config import settings
import redis.asyncio as redis
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.redis_url = settings.REDIS_URL
        self.pubsub_channel = "tempo_ws_updates"

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        # Local broadcast (for same process)
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error local broadcasting to WebSocket: {e}")
        
    async def publish_broadcast(self, message: str):
        """Publishes a message to Redis so all instances/processes broadcast it."""
        r = redis.from_url(self.redis_url)
        await r.publish(self.pubsub_channel, message)
        await r.close()

    def publish_broadcast_sync(self, message: str):
        """Synchronous version of publish_broadcast."""
        import redis as redis_sync
        r = redis_sync.from_url(self.redis_url)
        r.publish(self.pubsub_channel, message)
        r.close()

    async def listen_and_broadcast(self):
        """Listens to Redis and broadcasts messages to local connections."""
        r = redis.from_url(self.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(self.pubsub_channel)
        logger.info(f"Subscribed to Redis channel: {self.pubsub_channel}")
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"].decode("utf-8")
                    logger.info(f"Received Redis broadcast: {data}")
                    await self.broadcast(data)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Redis PubSub listener error: {e}")
        finally:
            await pubsub.unsubscribe(self.pubsub_channel)
            await r.close()

manager = ConnectionManager()
