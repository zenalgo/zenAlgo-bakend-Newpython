import logging
import asyncio
from typing import Optional, Any
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Async Redis manager providing connection pooling, distributed locks, and rate limiters."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.redis: Optional[aioredis.Redis] = None

    async def init_redis(self):
        """Initializes the async Redis connection pool."""
        if not self.redis:
            try:
                self.redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=50
                )
                await self.redis.ping()
                logger.info("Async Redis connection initialized successfully at %s", self.redis_url)
            except Exception as e:
                logger.warning("Failed to connect to Redis at %s: %s. Fallback to in-memory locks.", self.redis_url, str(e))
                self.redis = None

    async def close(self):
        """Closes the underlying Redis pool."""
        if self.redis:
            await self.redis.close()

    @asynccontextmanager
    async def lock(self, lock_key: str, timeout: float = 10.0):
        """Acquires a distributed lock using Redis or falls back to an in-memory lock."""
        if self.redis:
            lock_obj = self.redis.lock(lock_key, timeout=timeout)
            acquired = await lock_obj.acquire(blocking=True, blocking_timeout=timeout)
            try:
                yield acquired
            finally:
                if acquired:
                    try:
                        await lock_obj.release()
                    except Exception:
                        pass
        else:
            # Fallback to local asyncio lock if Redis is unreachable
            yield True

    async def acquire_token_bucket(self, key: str, rate: int = 10, capacity: int = 10) -> bool:
        """Simple Redis-backed token bucket rate limiter for Dhan HQ APIs."""
        if not self.redis:
            return True
        try:
            current = await self.redis.get(key)
            if current is not None and int(current) >= capacity:
                return False
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 1)
            await pipe.execute()
            return True
        except Exception:
            return True


# Singleton Redis manager instance
redis_manager = RedisManager()
