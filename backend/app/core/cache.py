"""
Simple in-memory caching utilities for API responses.
For production, consider Redis or similar distributed cache.
"""

import hashlib
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional


class LRUCache:
    """Simple LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if not expired."""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache with TTL."""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl

        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, expiry)

        # Evict oldest items if over capacity
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """Delete a key from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern (simple prefix match)."""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


# Global cache instance
_cache = LRUCache(max_size=1000, default_ttl=300)


def cached(ttl: int = 300, prefix: str = "") -> Callable:
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live in seconds
        prefix: Optional prefix for cache key
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip caching for certain conditions
            skip_cache = kwargs.pop("_skip_cache", False)
            if skip_cache:
                return await func(*args, **kwargs)

            key = f"{prefix}:{func.__name__}:{_cache._make_key(*args, **kwargs)}"
            result = _cache.get(key)

            if result is not None:
                return result

            result = await func(*args, **kwargs)
            _cache.set(key, result, ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            skip_cache = kwargs.pop("_skip_cache", False)
            if skip_cache:
                return func(*args, **kwargs)

            key = f"{prefix}:{func.__name__}:{_cache._make_key(*args, **kwargs)}"
            result = _cache.get(key)

            if result is not None:
                return result

            result = func(*args, **kwargs)
            _cache.set(key, result, ttl)
            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache(prefix: str) -> int:
    """Invalidate all cache entries matching prefix."""
    return _cache.invalidate_pattern(prefix)


def clear_cache() -> None:
    """Clear all cache entries."""
    _cache.clear()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "size": len(_cache._cache),
        "max_size": _cache.max_size,
        "default_ttl": _cache.default_ttl,
    }
