from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Automated site layout generation API for BESS projects",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Site Layout API",
        "version": settings.VERSION,
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
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


# API routers will be added here
# from app.api import auth, projects, files, terrain, assets

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
