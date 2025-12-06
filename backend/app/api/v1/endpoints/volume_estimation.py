"""API endpoints for cut/fill volume estimation."""

import hashlib
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.crud.asset_placement import asset_placement as placement_crud
from app.crud.project import project as project_crud
from app.crud.road_network import road_network as road_crud
from app.crud.terrain_analysis import terrain_analysis as terrain_crud
from app.crud.uploaded_file import uploaded_file as file_crud
from app.crud.volume_estimation import volume_estimation as volume_crud
from app.db.base import get_db
from app.models.user import User
from app.models.volume_estimation import VolumeEstimationStatus
from app.schemas.volume_estimation import (
    VisualizationDataResponse,
    VolumeEstimationCreate,
    VolumeEstimationDetailResponse,
    VolumeEstimationListResponse,
    VolumeEstimationResponse,
    VolumetricReportResponse,
)
from app.services.volume_estimation import estimate_volumes, generate_volumetric_report

router = APIRouter()


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


def calculate_input_hash(
    terrain_id: UUID,
    placement_id: Optional[UUID],
    road_id: Optional[UUID],
    grid_resolution: float,
    foundation_type: str,
    road_width: float,
) -> str:
    """Calculate hash of input parameters for caching."""
    hash_input = (
        f"{terrain_id}:{placement_id}:{road_id}:"
        f"{grid_resolution:.2f}:{foundation_type}:{road_width:.2f}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()


@router.post(
    "/projects/{project_id}/volumes/estimate",
    response_model=VolumeEstimationResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_volume_estimation(
    project_id: UUID,
    estimation_in: VolumeEstimationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Request a new cut/fill volume estimation for a project.

    Requires at least one of:
    - terrain_analysis_id: For DEM data
    - asset_placement_id: For asset positions to calculate foundation volumes
    - road_network_id: For road segments to calculate road earthwork

    The estimation will calculate:
    - Cut (excavation) volumes for each asset foundation
    - Fill volumes for each asset foundation
    - Cut/fill volumes for road construction
    - Total project earthwork balance
    - 3D visualization data for cut/fill areas
    """
    verify_project_access(db, project_id, current_user)

    # Validate inputs - need at least terrain + (assets or roads)
    if not estimation_in.terrain_analysis_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="terrain_analysis_id is required for DEM data",
        )

    if not estimation_in.asset_placement_id and not estimation_in.road_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="asset_placement_id or road_network_id required",
        )

    # Get terrain analysis for DEM path
    terrain = terrain_crud.get(db, analysis_id=estimation_in.terrain_analysis_id)
    if not terrain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found",
        )
    if terrain.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terrain analysis not found in this project",
        )

    # Get DEM file path
    if not terrain.source_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terrain analysis has no associated DEM file",
        )

    uploaded_file = file_crud.get(db, file_id=terrain.source_file_id)
    if not uploaded_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DEM file not found",
        )
    dem_path = uploaded_file.file_path

    # Get asset positions if provided
    asset_positions = []
    if estimation_in.asset_placement_id:
        pid = estimation_in.asset_placement_id
        placement = placement_crud.get(db, placement_id=pid)
        if not placement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset placement not found",
            )
        if placement.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset placement not in this project",
            )

        # Extract asset positions from placement details
        if placement.placement_details and "assets" in placement.placement_details:
            for asset in placement.placement_details["assets"]:
                asset_positions.append(
                    {
                        "id": asset.get("id", 0),
                        "position": asset.get("position", [0, 0]),
                        "rotation": asset.get("rotation", 0.0),
                        "foundation_type": estimation_in.default_foundation_type,
                    }
                )

    # Get road segments if provided
    road_segments = None
    if estimation_in.road_network_id:
        road = road_crud.get(db, network_id=estimation_in.road_network_id)
        if not road:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Road network not found",
            )
        if road.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Road network not in this project",
            )

        # Extract road segments from road details
        if road.road_details and "segments" in road.road_details:
            road_segments = road.road_details["segments"]

    # Check for cached results
    input_hash = calculate_input_hash(
        estimation_in.terrain_analysis_id,
        estimation_in.asset_placement_id,
        estimation_in.road_network_id,
        estimation_in.grid_resolution,
        estimation_in.default_foundation_type,
        estimation_in.road_width,
    )
    cached = volume_crud.get_by_input_hash(db, project_id, input_hash)

    if cached:
        # Return cached result with CACHED status
        cached.status = VolumeEstimationStatus.CACHED
        db.commit()
        return volume_crud.to_response_dict(cached)

    # Create estimation record
    estimation = volume_crud.create(
        db, project_id=project_id, estimation_in=estimation_in
    )

    # Update status to processing
    volume_crud.update_status(
        db, estimation, VolumeEstimationStatus.PROCESSING, 0, "Starting estimation"
    )

    # Perform estimation
    # Note: For production, this should be moved to a background task queue
    def progress_callback(percent: int, step: str):
        volume_crud.update_status(
            db, estimation, VolumeEstimationStatus.PROCESSING, percent, step
        )

    result = estimate_volumes(
        asset_positions=asset_positions,
        road_segments=road_segments,
        dem_path=dem_path,
        grid_resolution=estimation_in.grid_resolution,
        foundation_type=estimation_in.default_foundation_type,
        road_width=estimation_in.road_width,
        include_visualization=estimation_in.include_visualization,
        progress_callback=progress_callback,
    )

    # Update with results
    estimation = volume_crud.update_with_results(db, estimation, result, input_hash)

    # Generate report if successful
    if result.success:
        project = project_crud.get(db, project_id=project_id)
        proj_name = project.name if project else "Project"
        report = generate_volumetric_report(result, proj_name)
        estimation.report_data = report
        db.add(estimation)
        db.commit()
        db.refresh(estimation)

    return volume_crud.to_response_dict(estimation)


@router.get(
    "/projects/{project_id}/volumes",
    response_model=VolumeEstimationListResponse,
)
def list_volume_estimations(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all volume estimations for a project.
    """
    verify_project_access(db, project_id, current_user)

    skip = (page - 1) * page_size
    estimations = volume_crud.get_by_project(
        db, project_id=project_id, skip=skip, limit=page_size
    )
    total = volume_crud.get_count_by_project(db, project_id=project_id)

    return {
        "estimations": [volume_crud.to_response_dict(e) for e in estimations],
        "total": total,
    }


@router.get(
    "/projects/{project_id}/volumes/{estimation_id}",
    response_model=VolumeEstimationResponse,
)
def get_volume_estimation(
    project_id: UUID,
    estimation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get a specific volume estimation summary.
    """
    verify_project_access(db, project_id, current_user)

    estimation = volume_crud.get(db, estimation_id=estimation_id)
    if not estimation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found",
        )
    if estimation.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found in this project",
        )

    return volume_crud.to_response_dict(estimation)


@router.get(
    "/projects/{project_id}/volumes/{estimation_id}/details",
    response_model=VolumeEstimationDetailResponse,
)
def get_volume_estimation_details(
    project_id: UUID,
    estimation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get detailed volume estimation including per-asset and per-segment breakdowns.
    """
    verify_project_access(db, project_id, current_user)

    estimation = volume_crud.get(db, estimation_id=estimation_id)
    if not estimation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found",
        )
    if estimation.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found in this project",
        )

    return volume_crud.to_response_dict(estimation, include_details=True)


@router.get(
    "/projects/{project_id}/volumes/{estimation_id}/report",
    response_model=VolumetricReportResponse,
)
def get_volumetric_report(
    project_id: UUID,
    estimation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get the volumetric report with project totals and breakdowns.
    """
    verify_project_access(db, project_id, current_user)

    estimation = volume_crud.get(db, estimation_id=estimation_id)
    if not estimation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found",
        )
    if estimation.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found in this project",
        )

    if not estimation.report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not available for this estimation",
        )

    return estimation.report_data


@router.get(
    "/projects/{project_id}/volumes/{estimation_id}/visualization",
    response_model=VisualizationDataResponse,
)
def get_visualization_data(
    project_id: UUID,
    estimation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get 3D visualization data for cut/fill areas.
    """
    verify_project_access(db, project_id, current_user)

    estimation = volume_crud.get(db, estimation_id=estimation_id)
    if not estimation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found",
        )
    if estimation.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found in this project",
        )

    if not estimation.visualization_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visualization data not available for this estimation",
        )

    return estimation.visualization_data


@router.delete(
    "/projects/{project_id}/volumes/{estimation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_volume_estimation(
    project_id: UUID,
    estimation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete a volume estimation.
    """
    verify_project_access(db, project_id, current_user)

    estimation = volume_crud.get(db, estimation_id=estimation_id)
    if not estimation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found",
        )
    if estimation.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volume estimation not found in this project",
        )

    volume_crud.delete(db, estimation_id=estimation_id)
    return None
