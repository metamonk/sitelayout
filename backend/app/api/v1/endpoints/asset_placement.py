"""API endpoints for asset auto-placement."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.crud.asset_placement import asset_placement as placement_crud
from app.crud.exclusion_zone import exclusion_zone as zone_crud
from app.crud.project import project as project_crud
from app.crud.terrain_analysis import terrain_analysis as terrain_crud
from app.db.base import get_db
from app.models.asset_placement import PlacementStatus
from app.models.user import User
from app.schemas.asset_placement import (
    AssetAdjustmentRequest,
    AssetPlacementCreate,
    AssetPlacementListResponse,
    AssetPlacementResponse,
    AssetPlacementUpdate,
)
from app.services.asset_placement import place_assets

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


@router.post(
    "/projects/{project_id}/asset-placements",
    response_model=AssetPlacementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_placement(
    project_id: UUID,
    placement_in: AssetPlacementCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Create a new asset placement request.

    This endpoint initiates the auto-placement algorithm to optimally place
    BESS assets within the specified area, respecting terrain constraints
    and exclusion zones.

    The algorithm will:
    1. Generate a grid of candidate locations
    2. Filter based on slope, exclusion zones, and other constraints
    3. Optimize placement according to the specified criteria
    4. Return the placed asset locations

    Processing may take up to 60 seconds for complex sites with 500 locations.
    """
    verify_project_access(db, project_id, current_user)

    # Validate terrain analysis if provided
    if placement_in.terrain_analysis_id:
        terrain = terrain_crud.get(db, analysis_id=placement_in.terrain_analysis_id)
        if not terrain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Terrain analysis not found",
            )
        if terrain.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Terrain analysis does not belong to this project",
            )

    # Create placement record
    placement = placement_crud.create(
        db,
        project_id=project_id,
        user_id=current_user.id,
        placement_in=placement_in,
    )

    # Update status to processing
    placement_crud.update_status(
        db, placement, PlacementStatus.PROCESSING, 0, "Starting placement algorithm"
    )

    # Get placement area (use project boundary if not provided)
    placement_area = placement_in.placement_area
    if not placement_area:
        project = project_crud.get(db, project_id=project_id)
        if project and project.boundary_geom:
            from geoalchemy2.shape import to_shape
            from shapely.geometry import mapping

            boundary_shape = to_shape(project.boundary_geom)
            placement_area = mapping(boundary_shape)
        else:
            placement_crud.update_status(
                db,
                placement,
                PlacementStatus.FAILED,
                0,
                error_message="No placement area provided and project has no boundary",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No placement area provided and project has no boundary",
            )

    # Get slope raster path if terrain analysis is available
    slope_raster_path = None
    if placement_in.terrain_analysis_id:
        terrain = terrain_crud.get(db, analysis_id=placement_in.terrain_analysis_id)
        if terrain:
            slope_raster_path = terrain.slope_raster_path

    # Get exclusion zones for the project
    exclusion_zones_db = zone_crud.get_by_project(db, project_id, active_only=True)
    exclusion_zones = []
    for zone in exclusion_zones_db:
        zone_dict = zone_crud.to_response_dict(zone)
        # Use buffered geometry if available, otherwise use regular geometry
        geom = zone_dict.get("buffered_geometry") or zone_dict.get("geometry")
        if geom:
            exclusion_zones.append(geom)

    # Progress callback
    def progress_callback(percent: int, step: str):
        placement_crud.update_status(
            db, placement, PlacementStatus.PROCESSING, percent, step
        )

    # Ensure placement_area is not None
    if not placement_area:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Placement area is required",
        )

    # Run placement algorithm
    # Note: For production, this should be moved to a background task queue
    result = place_assets(
        placement_area=placement_area,
        num_assets=placement_in.asset_count,
        grid_resolution=placement_in.grid_resolution,
        min_spacing=placement_in.min_spacing,
        max_slope=placement_in.max_slope,
        optimization_criteria=placement_in.optimization_criteria,
        slope_raster_path=slope_raster_path,
        exclusion_zones=exclusion_zones,
        advanced_settings=placement_in.advanced_settings,
        progress_callback=progress_callback,
    )

    # Convert result to dictionary format expected by CRUD
    result_dict = {
        "success": result.success,
        "placed_positions": result.placed_positions,
        "placement_details": result.placement_details,
        "assets_placed": result.assets_placed,
        "placement_success_rate": result.placement_success_rate,
        "grid_cells_total": result.grid_cells_total,
        "grid_cells_valid": result.grid_cells_valid,
        "grid_cells_excluded": result.grid_cells_excluded,
        "avg_slope": result.avg_slope,
        "avg_inter_asset_distance": result.avg_inter_asset_distance,
        "total_cut_fill_volume": result.total_cut_fill_volume,
        "processing_time": result.processing_time,
        "memory_peak_mb": result.memory_peak_mb,
        "algorithm_iterations": result.algorithm_iterations,
        "error_message": result.error_message,
    }

    # Update with results
    placement = placement_crud.update_with_results(db, placement, result_dict)

    return placement_crud.to_response_dict(placement)


@router.get(
    "/projects/{project_id}/asset-placements",
    response_model=AssetPlacementListResponse,
)
def list_asset_placements(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all asset placements for a project.
    """
    verify_project_access(db, project_id, current_user)

    skip = (page - 1) * page_size
    placements = placement_crud.get_by_project(
        db, project_id=project_id, skip=skip, limit=page_size
    )
    total = placement_crud.get_count_by_project(db, project_id=project_id)

    return {
        "placements": [placement_crud.to_response_dict(p) for p in placements],
        "total": total,
    }


@router.get(
    "/projects/{project_id}/asset-placements/{placement_id}",
    response_model=AssetPlacementResponse,
)
def get_asset_placement(
    project_id: UUID,
    placement_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get a specific asset placement.
    """
    verify_project_access(db, project_id, current_user)

    placement = placement_crud.get(db, placement_id=placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found",
        )
    if placement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found in this project",
        )

    return placement_crud.to_response_dict(placement)


@router.patch(
    "/projects/{project_id}/asset-placements/{placement_id}",
    response_model=AssetPlacementResponse,
)
def update_asset_placement(
    project_id: UUID,
    placement_id: UUID,
    update_in: AssetPlacementUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Update an asset placement (e.g., name, description, or manual adjustments).
    """
    verify_project_access(db, project_id, current_user)

    placement = placement_crud.get(db, placement_id=placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found",
        )
    if placement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found in this project",
        )

    # Update fields
    if update_in.name is not None:
        placement.name = update_in.name
    if update_in.description is not None:
        placement.description = update_in.description
    if update_in.placement_details is not None:
        placement = placement_crud.update_placement_details(
            db, placement, update_in.placement_details
        )

    db.add(placement)
    db.commit()
    db.refresh(placement)

    return placement_crud.to_response_dict(placement)


@router.post(
    "/projects/{project_id}/asset-placements/{placement_id}/adjust",
    response_model=AssetPlacementResponse,
)
def adjust_assets(
    project_id: UUID,
    placement_id: UUID,
    adjustments: AssetAdjustmentRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Manually adjust positions of placed assets.

    This endpoint allows fine-tuning the auto-placement results by
    manually moving individual assets to different locations.
    """
    verify_project_access(db, project_id, current_user)

    placement = placement_crud.get(db, placement_id=placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found",
        )
    if placement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found in this project",
        )

    # Get current placement details
    if not placement.placement_details or "assets" not in placement.placement_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No placement details available to adjust",
        )

    assets = placement.placement_details["assets"]

    # Apply adjustments
    for adjustment in adjustments.adjustments:
        # Find the asset by ID
        asset = next((a for a in assets if a["id"] == adjustment.asset_id), None)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset {adjustment.asset_id} not found in placement",
            )

        # Update position
        asset["position"] = adjustment.new_position

        # Update rotation if provided
        if adjustment.new_rotation is not None:
            asset["rotation"] = adjustment.new_rotation

    # Save updated placement details
    updated_details = {"assets": assets}
    placement = placement_crud.update_placement_details(db, placement, updated_details)

    return placement_crud.to_response_dict(placement)


@router.delete(
    "/projects/{project_id}/asset-placements/{placement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_asset_placement(
    project_id: UUID,
    placement_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete an asset placement.
    """
    verify_project_access(db, project_id, current_user)

    placement = placement_crud.get(db, placement_id=placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found",
        )
    if placement.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset placement not found in this project",
        )

    placement_crud.delete(db, placement_id=placement_id)
    return None
