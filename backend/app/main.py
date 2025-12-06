from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    APIError,
    api_error_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    setup_logging,
)

# Setup logging
setup_logging()

# Create FastAPI application
fastapi_app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Automated site layout generation API for BESS projects",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (use FastAPI's built-in for compatibility)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
fastapi_app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
fastapi_app.add_exception_handler(
    HTTPException, http_exception_handler  # type: ignore[arg-type]
)
fastapi_app.add_exception_handler(
    RequestValidationError, validation_exception_handler  # type: ignore[arg-type]
)
fastapi_app.add_exception_handler(Exception, generic_exception_handler)

# Include API v1 router (auth, projects, etc.)
fastapi_app.include_router(api_router, prefix=settings.API_V1_STR)


@fastapi_app.get("/")
async def root():
    return {
        "message": "Site Layout API",
        "version": settings.VERSION,
        "status": "operational",
    }


@fastapi_app.get("/health")
async def health_check():
    return {"status": "healthy"}


@fastapi_app.get("/health/db")
async def database_health_check():
    """Check database connectivity."""
    from sqlalchemy import text

    from app.db.base import engine

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            # Also check PostGIS
            postgis_result = conn.execute(text("SELECT PostGIS_Version()"))
            postgis_version = postgis_result.fetchone()[0]
        return {
            "status": "healthy",
            "database": "connected",
            "postgis_version": postgis_version,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


# Wrap app with pure ASGI middleware (order: outermost first)
# RequestLoggingMiddleware wraps RateLimitMiddleware wraps fastapi_app
app = RequestLoggingMiddleware(
    RateLimitMiddleware(fastapi_app, max_requests=100, window_seconds=60)
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
