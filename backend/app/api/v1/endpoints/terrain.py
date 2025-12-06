"""API endpoints for terrain analysis."""

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.crud.project import project as project_crud
from app.crud.terrain_analysis import terrain_analysis as terrain_crud
from app.crud.uploaded_file import uploaded_file as file_crud
from app.db.base import get_db
from app.models.terrain_analysis import AnalysisStatus
from app.models.user import User
from app.schemas.terrain import (
    ElevationAtPointsRequest,
    ElevationAtPointsResponse,
    TerrainAnalysisCreate,
    TerrainAnalysisListResponse,
    TerrainAnalysisResponse,
    TerrainProfileRequest,
    TerrainProfileResponse,
)
from app.services.terrain_analysis import (
    analyze_terrain,
    calculate_input_hash,
    get_elevation_at_points,
    get_terrain_profile,
)

router = APIRouter()

# Output directory for terrain analysis results
TERRAIN_OUTPUT_DIR = os.path.join(settings.UPLOAD_DIR, "terrain_analysis")


def verify_project_access(
    db: Session,
    project_id: UUID,
    user: User,
) -> None:
    """Verify user has access to the project."""
    project = project_crud.get(db, project_id=project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )


@router.post(
    "/projects/{project_id}/terrain/analyze",
    response_model=TerrainAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_terrain_analysis(
    project_id: UUID,
    analysis_in: TerrainAnalysisCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Request a new terrain analysis for a project.

    Requires either a source_file_id (UUID of an uploaded DEM file) or
    dem_url (URL to external DEM source).

    The analysis will calculate:
    - Elevation statistics (min, max, mean, std)
    - Slope analysis with classification
    - Aspect analysis with directional distribution
    - Hillshade visualization

    Analysis results are cached for 7 days based on input parameters.
    """
    verify_project_access(db, project_id, current_user)

    # Validate input
    if not analysis_in.source_file_id and not analysis_in.dem_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either source_file_id or dem_url must be provided",
        )

    # Get DEM file path
    dem_path = None
    if analysis_in.source_file_id:
        uploaded_file = file_crud.get(db, file_id=analysis_in.source_file_id)
        if not uploaded_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file not found",
            )
        if uploaded_file.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this file",
            )
        dem_path = uploaded_file.file_path
    elif analysis_in.dem_url:
        # TODO: Download DEM from URL
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="DEM URL download not yet implemented",
        )

    # Check for cached results
    bounds_tuple: tuple[float, float, float, float] | None = (
        tuple(analysis_in.bounds) if analysis_in.bounds else None  # type: ignore[assignment]
    )
    input_hash = calculate_input_hash(dem_path, bounds_tuple) if dem_path else ""
    cached = terrain_crud.get_by_input_hash(db, project_id, input_hash)

    if cached:
        # Return cached result with CACHED status
        cached.status = AnalysisStatus.CACHED
        db.commit()
        return terrain_crud.to_response_dict(cached)

    # Create analysis record
    analysis = terrain_crud.create(db, project_id=project_id, analysis_in=analysis_in)

    # Update status to processing
    terrain_crud.update_status(
        db, analysis, AnalysisStatus.PROCESSING, 0, "Starting analysis"
    )

    # Create output directory
    output_dir = os.path.join(TERRAIN_OUTPUT_DIR, str(project_id))
    os.makedirs(output_dir, exist_ok=True)

    # Perform analysis
    # Note: For production, this should be moved to a background task queue
    def progress_callback(percent: int, step: str):
        terrain_crud.update_status(
            db, analysis, AnalysisStatus.PROCESSING, percent, step
        )

    result = analyze_terrain(
        dem_path=dem_path,  # type: ignore[arg-type]
        output_dir=output_dir,
        analysis_id=str(analysis.id),
        bounds=bounds_tuple,
        progress_callback=progress_callback,
    )

    # Update with results
    analysis = terrain_crud.update_with_results(db, analysis, result)

    return terrain_crud.to_response_dict(analysis)


@router.get(
    "/projects/{project_id}/terrain",
    response_model=TerrainAnalysisListResponse,
)
def list_terrain_analyses(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all terrain analyses for a project.
    """
    verify_project_access(db, project_id, current_user)

    skip = (page - 1) * page_size
    analyses = terrain_crud.get_by_project(
        db, project_id=project_id, skip=skip, limit=page_size
    )
    total = terrain_crud.get_count_by_project(db, project_id=project_id)

    return {
        "analyses": [terrain_crud.to_response_dict(a) for a in analyses],
        "total": total,
    }


@router.get(
    "/projects/{project_id}/terrain/{analysis_id}",
    response_model=TerrainAnalysisResponse,
)
def get_terrain_analysis(
    project_id: UUID,
    analysis_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get a specific terrain analysis.
    """
    verify_project_access(db, project_id, current_user)

    analysis = terrain_crud.get(db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )
    if analysis.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found in this project",
        )

    return terrain_crud.to_response_dict(analysis)


@router.delete(
    "/projects/{project_id}/terrain/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_terrain_analysis(
    project_id: UUID,
    analysis_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete a terrain analysis and its associated files.
    """
    verify_project_access(db, project_id, current_user)

    analysis = terrain_crud.get(db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )
    if analysis.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found in this project",
        )

    # Delete associated raster files
    for path in [
        analysis.slope_raster_path,
        analysis.aspect_raster_path,
        analysis.hillshade_raster_path,
    ]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    terrain_crud.delete(db, analysis_id=analysis_id)
    return None


@router.get(
    "/projects/{project_id}/terrain/{analysis_id}/raster/{raster_type}",
)
def download_terrain_raster(
    project_id: UUID,
    analysis_id: UUID,
    raster_type: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Download a generated terrain raster file.

    raster_type can be: slope, aspect, or hillshade
    """
    verify_project_access(db, project_id, current_user)

    analysis = terrain_crud.get(db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )
    if analysis.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found in this project",
        )

    # Get the appropriate raster path
    raster_paths = {
        "slope": analysis.slope_raster_path,
        "aspect": analysis.aspect_raster_path,
        "hillshade": analysis.hillshade_raster_path,
    }

    if raster_type not in raster_paths:
        valid_types = ", ".join(raster_paths.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid raster type. Must be one of: {valid_types}",
        )

    raster_path = raster_paths[raster_type]
    if not raster_path or not os.path.exists(raster_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{raster_type.capitalize()} raster not available",
        )

    return FileResponse(
        path=raster_path,
        filename=f"{analysis_id}_{raster_type}.tif",
        media_type="image/tiff",
    )


@router.post(
    "/projects/{project_id}/terrain/{analysis_id}/profile",
    response_model=TerrainProfileResponse,
)
def get_terrain_profile_endpoint(
    project_id: UUID,
    analysis_id: UUID,
    request: TerrainProfileRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get elevation profile along a line.
    """
    verify_project_access(db, project_id, current_user)

    analysis = terrain_crud.get(db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )

    # Get the DEM path from the source file
    if not analysis.source_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DEM file associated with this analysis",
        )

    uploaded_file = file_crud.get(db, file_id=analysis.source_file_id)
    if not uploaded_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source DEM file not found",
        )

    start_pt: tuple[float, float] = (request.start_point[0], request.start_point[1])
    end_pt: tuple[float, float] = (request.end_point[0], request.end_point[1])
    profile = get_terrain_profile(
        dem_path=uploaded_file.file_path,
        start_point=start_pt,
        end_point=end_pt,
        num_samples=request.num_samples,
    )

    return profile


@router.post(
    "/projects/{project_id}/terrain/{analysis_id}/elevations",
    response_model=ElevationAtPointsResponse,
)
def get_elevations_at_points(
    project_id: UUID,
    analysis_id: UUID,
    request: ElevationAtPointsRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get elevation values at specific points.
    """
    verify_project_access(db, project_id, current_user)

    analysis = terrain_crud.get(db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )

    # Get the DEM path from the source file
    if not analysis.source_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DEM file associated with this analysis",
        )

    uploaded_file = file_crud.get(db, file_id=analysis.source_file_id)
    if not uploaded_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source DEM file not found",
        )

    points = [(p[0], p[1]) for p in request.points]
    elevations = get_elevation_at_points(uploaded_file.file_path, points)

    return {"elevations": elevations}
