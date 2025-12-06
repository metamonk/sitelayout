from fastapi import APIRouter

from app.api.v1.endpoints import (
    asset_placement,
    auth,
    exclusion_zones,
    exports,
    files,
    projects,
    road_network,
    terrain,
    volume_estimation,
)

api_router = APIRouter()

# Include authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include file upload routes
api_router.include_router(files.router, prefix="/files", tags=["files"])

# Include project management routes
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

# Include terrain analysis routes
api_router.include_router(terrain.router, tags=["terrain"])

# Include exclusion zone routes
api_router.include_router(
    exclusion_zones.router, prefix="/projects", tags=["exclusion-zones"]
)

# Include asset placement routes
api_router.include_router(asset_placement.router, tags=["asset-placement"])

# Include road network routes
api_router.include_router(road_network.router, tags=["road-network"])

# Include volume estimation routes
api_router.include_router(volume_estimation.router, tags=["volume-estimation"])

# Include export routes
api_router.include_router(exports.router, tags=["exports"])
