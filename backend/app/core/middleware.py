"""
Middleware for API security, rate limiting, and request logging.
"""

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

# Configure logger
logger = logging.getLogger("sitelayout.api")


class RequestLoggingMiddleware:
    """
    Pure ASGI middleware for logging all HTTP requests and responses.
    Uses pure ASGI to avoid BaseHTTPMiddleware issues with streaming.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate request ID for tracing
        request_id = str(uuid4())[:8]
        start_time = time.time()

        # Get request info
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # Store request_id in scope for later access
        scope["state"] = {"request_id": request_id}

        # Log request
        logger.info(f"[{request_id}] {method} {path} - Client: {client_ip}")

        # Track response status
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add custom headers
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                process_time = time.time() - start_time
                headers.append((b"x-process-time", f"{process_time:.3f}".encode()))
                message = {**message, "headers": headers}
            await send(message)

            # Log response when body is sent
            if message["type"] == "http.response.body":
                process_time = time.time() - start_time
                logger.info(
                    f"[{request_id}] {method} {path} "
                    f"- Status: {status_code} - Time: {process_time:.3f}s"
                )

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"[{request_id}] {method} {path} "
                f"- Error: {str(e)} - Time: {process_time:.3f}s"
            )
            raise


class RateLimitState:
    """Simple in-memory rate limit tracking."""

    def __init__(self):
        self.requests: dict[str, list[float]] = {}

    def is_rate_limited(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if a key is rate limited.
        Returns (is_limited, remaining_requests).
        """
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries
        if key in self.requests:
            self.requests[key] = [ts for ts in self.requests[key] if ts > window_start]
        else:
            self.requests[key] = []

        # Check limit
        current_count = len(self.requests[key])
        if current_count >= max_requests:
            return True, 0

        # Record request
        self.requests[key].append(now)
        return False, max_requests - current_count - 1


# Global rate limit state
rate_limit_state = RateLimitState()


class RateLimitMiddleware:
    """
    Pure ASGI rate limiting middleware.
    Limits requests per IP address.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 100,
        window_seconds: int = 60,
        exempt_paths: list[str] | None = None,
    ):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or [
            "/health",
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip rate limiting for exempt paths
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        # Get client identifier (IP address)
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # Check rate limit
        is_limited, remaining = rate_limit_state.is_rate_limited(
            client_ip, self.max_requests, self.window_seconds
        )

        if is_limited:
            # Return 429 response
            response_body = b'{"detail": "Too many requests. Please try again later."}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"x-ratelimit-limit", str(self.max_requests).encode()),
                        (b"x-ratelimit-remaining", b"0"),
                        (b"x-ratelimit-reset", str(self.window_seconds).encode()),
                        (b"retry-after", str(self.window_seconds).encode()),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": response_body,
                }
            )
            return

        # Add rate limit headers to response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(self.max_requests).encode()))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                headers.append(
                    (b"x-ratelimit-reset", str(self.window_seconds).encode())
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_logging():
    """Configure application logging."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set specific loggers
    logging.getLogger("sitelayout").setLevel(log_level)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
