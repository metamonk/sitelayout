"""API endpoints for road network generation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.crud.asset_placement import asset_placement as placement_crud
from app.crud.exclusion_zone import exclusion_zone as zone_crud
from app.crud.project import project as project_crud
from app.crud.road_network import road_network as network_crud
from app.crud.terrain_analysis import terrain_analysis as terrain_crud
from app.db.base import get_db
from app.models.road_network import RoadNetworkStatus
from app.models.user import User
from app.schemas.road_network import (
    RoadNetworkAdjustmentRequest,
    RoadNetworkCreate,
    RoadNetworkListResponse,
    RoadNetworkResponse,
    RoadNetworkUpdate,
)
from app.services.road_network import generate_road_network

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
    "/projects/{project_id}/road-networks",
    response_model=RoadNetworkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_road_network(
    project_id: UUID,
    network_in: RoadNetworkCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Create a new road network generation request.

    This endpoint initiates the road network generation algorithm to connect
    placed assets with optimized roads, considering terrain constraints,
    grade limits, and exclusion zones.

    The algorithm will:
    1. Build a pathfinding grid over the site
    2. Load terrain elevation data for grade calculations
    3. Mark exclusion zones as impassable
    4. Use A* pathfinding to connect assets via minimum spanning tree
    5. Optimize paths based on selected criteria (length, earthwork, grade)
    6. Generate road centerlines and buffered polygons

    Processing may take up to 60 seconds for complex sites.
    """
    verify_project_access(db, project_id, current_user)

    # Validate terrain analysis if provided
    dem_path = None
    if network_in.terrain_analysis_id:
        terrain = terrain_crud.get(db, analysis_id=network_in.terrain_analysis_id)
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
        # Use the DEM source path if available
        # Use slope raster for elevation sampling
        dem_path = terrain.slope_raster_path

    # Validate asset placement if provided
    asset_positions = []
    if network_in.asset_placement_id:
        placement = placement_crud.get(db, placement_id=network_in.asset_placement_id)
        if not placement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset placement not found",
            )
        if placement.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Asset placement does not belong to this project",
            )
        # Extract asset positions from placement details
        if placement.placement_details and "assets" in placement.placement_details:
            for asset in placement.placement_details["assets"]:
                pos = asset.get("position")
                if pos and len(pos) >= 2:
                    asset_positions.append((pos[0], pos[1]))

    if not asset_positions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No asset positions. Ensure asset placement completed.",
        )

    # Create road network record
    network = network_crud.create(
        db,
        project_id=project_id,
        user_id=current_user.id,
        network_in=network_in,
    )

    # Update status to processing
    network_crud.update_status(
        db, network, RoadNetworkStatus.PROCESSING, 0, "Starting road network generation"
    )

    # Get entry point (from request or project)
    entry_point = None
    if network_in.entry_point:
        # Parse GeoJSON point
        coords = network_in.entry_point.get("coordinates")
        if coords and len(coords) >= 2:
            entry_point = (coords[0], coords[1])
    else:
        # Try to get from project
        project = project_crud.get(db, project_id=project_id)
        if project and project.entry_point_geom:
            entry_shape = to_shape(project.entry_point_geom)
            entry_point = (entry_shape.x, entry_shape.y)

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
        network_crud.update_status(
            db, network, RoadNetworkStatus.PROCESSING, percent, step
        )

    # Run road network generation
    # Note: For production, this should be moved to a background task queue
    result = generate_road_network(
        asset_positions=asset_positions,
        entry_point=entry_point,
        road_width=network_in.road_width,
        max_grade=network_in.max_grade,
        min_curve_radius=network_in.min_curve_radius,
        grid_resolution=network_in.grid_resolution,
        optimization_criteria=network_in.optimization_criteria,
        exclusion_buffer=network_in.exclusion_buffer,
        dem_path=dem_path,
        exclusion_zones=exclusion_zones,
        advanced_settings=network_in.advanced_settings,
        progress_callback=progress_callback,
    )

    # Convert result to dictionary format expected by CRUD
    result_dict = {
        "success": result.success,
        "road_centerlines": result.road_centerlines,
        "road_polygons": result.road_polygons,
        "road_details": result.road_details,
        "total_road_length": result.total_road_length,
        "total_segments": result.total_segments,
        "total_intersections": result.total_intersections,
        "avg_grade": result.avg_grade,
        "max_grade_actual": result.max_grade_actual,
        "grade_compliant": result.grade_compliant,
        "total_cut_volume": result.total_cut_volume,
        "total_fill_volume": result.total_fill_volume,
        "net_earthwork_volume": result.net_earthwork_volume,
        "assets_connected": result.assets_connected,
        "connectivity_rate": result.connectivity_rate,
        "processing_time": result.processing_time,
        "memory_peak_mb": result.memory_peak_mb,
        "algorithm_iterations": result.algorithm_iterations,
        "pathfinding_algorithm": result.pathfinding_algorithm,
        "error_message": result.error_message,
    }

    # Update with results
    network = network_crud.update_with_results(db, network, result_dict)

    return network_crud.to_response_dict(network)


@router.get(
    "/projects/{project_id}/road-networks",
    response_model=RoadNetworkListResponse,
)
def list_road_networks(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all road networks for a project.
    """
    verify_project_access(db, project_id, current_user)

    skip = (page - 1) * page_size
    networks = network_crud.get_by_project(
        db, project_id=project_id, skip=skip, limit=page_size
    )
    total = network_crud.get_count_by_project(db, project_id=project_id)

    return {
        "road_networks": [network_crud.to_response_dict(n) for n in networks],
        "total": total,
    }


@router.get(
    "/projects/{project_id}/road-networks/{network_id}",
    response_model=RoadNetworkResponse,
)
def get_road_network(
    project_id: UUID,
    network_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get a specific road network.
    """
    verify_project_access(db, project_id, current_user)

    network = network_crud.get(db, network_id=network_id)
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found",
        )
    if network.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found in this project",
        )

    return network_crud.to_response_dict(network)


@router.patch(
    "/projects/{project_id}/road-networks/{network_id}",
    response_model=RoadNetworkResponse,
)
def update_road_network(
    project_id: UUID,
    network_id: UUID,
    update_in: RoadNetworkUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Update a road network (e.g., name, description, or manual adjustments).
    """
    verify_project_access(db, project_id, current_user)

    network = network_crud.get(db, network_id=network_id)
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found",
        )
    if network.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found in this project",
        )

    # Update fields
    if update_in.name is not None:
        network.name = update_in.name
    if update_in.description is not None:
        network.description = update_in.description
    if update_in.road_details is not None:
        network = network_crud.update_road_details(db, network, update_in.road_details)

    db.add(network)
    db.commit()
    db.refresh(network)

    return network_crud.to_response_dict(network)


@router.post(
    "/projects/{project_id}/road-networks/{network_id}/adjust",
    response_model=RoadNetworkResponse,
)
def adjust_road_segments(
    project_id: UUID,
    network_id: UUID,
    adjustments: RoadNetworkAdjustmentRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Manually adjust road segment coordinates.

    This endpoint allows fine-tuning the road network by manually
    adjusting segment paths.
    """
    verify_project_access(db, project_id, current_user)

    network = network_crud.get(db, network_id=network_id)
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found",
        )
    if network.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found in this project",
        )

    # Get current road details
    if not network.road_details or "segments" not in network.road_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No road details available to adjust",
        )

    segments = network.road_details["segments"]

    # Apply adjustments
    for adjustment in adjustments.adjustments:
        # Find the segment by ID
        segment = next((s for s in segments if s["id"] == adjustment.segment_id), None)
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment {adjustment.segment_id} not found in road network",
            )

        # Update coordinates (add elevation if not present)
        new_coords = []
        for coord in adjustment.new_coordinates:
            if len(coord) >= 3:
                new_coords.append(coord)
            else:
                # Use 0 elevation if not provided
                new_coords.append([coord[0], coord[1], 0.0])
        segment["coordinates"] = new_coords

    # Save updated road details
    updated_details = {
        "segments": segments,
        "intersections": network.road_details.get("intersections", []),
    }
    network = network_crud.update_road_details(db, network, updated_details)

    return network_crud.to_response_dict(network)


@router.delete(
    "/projects/{project_id}/road-networks/{network_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_road_network(
    project_id: UUID,
    network_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete a road network.
    """
    verify_project_access(db, project_id, current_user)

    network = network_crud.get(db, network_id=network_id)
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found",
        )
    if network.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road network not found in this project",
        )

    network_crud.delete(db, network_id=network_id)
    return None
