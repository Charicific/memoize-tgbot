import json
import logging
from typing import Optional, Any
from redis.asyncio import Redis
from aiogram.fsm.storage.redis import RedisStorage
from src.config import settings

logger = logging.getLogger(__name__)

class RedisCacheManager:
    def __init__(self):
        # Initialize the redis client from connection URL
        self.client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Create aiogram FSM storage using the same redis client
        self.fsm_storage = RedisStorage(self.client)

    async def get(self, key: str) -> Optional[Any]:
        try:
            val = await self.client.get(key)
            if val:
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return val
            return None
        except Exception as e:
            logger.error(f"Redis get error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        try:
            val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            await self.client.set(key, val_str, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis set error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error for {key}: {e}")
            return False

    async def is_rate_limited(self, user_id: int, command: str, limit: int = 5, period: int = 60) -> bool:
        """
        Implements a simple sliding window / token bucket rate limiter in Redis.
        Returns True if the user is rate limited, False otherwise.
        """
        key = f"ratelimit:{user_id}:{command}"
        try:
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(key, period)
            return count > limit
        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            return False

    async def close(self):
        await self.client.aclose()

# Global instances can be initialized later
cache_manager = RedisCacheManager()
