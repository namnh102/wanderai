import redis.asyncio as redis
from app.config import settings
import json
from typing import Any

class CacheService:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )

    def normalize_key(self, key: str) -> str:
        return key.lower().replace(" ", "_")

    async def get(self, key: str) -> Any:
        try:
            norm_key = self.normalize_key(key)
            val = await self.redis.get(norm_key)
            if val:
                return json.loads(val)
            return None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            norm_key = self.normalize_key(key)
            await self.redis.set(norm_key, json.dumps(value), ex=ttl)
            return True
        except Exception:
            return False
