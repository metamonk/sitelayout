from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.crud.exclusion_zone import exclusion_zone as crud_exclusion_zone
from app.crud.project import project as crud_project
from app.crud.uploaded_file import uploaded_file as crud_uploaded_file
from app.models.user import User
from app.schemas.exclusion_zone import (
    BufferApplyRequest,
    ExclusionZoneCreate,
    ExclusionZoneImportRequest,
    ExclusionZoneImportResponse,
    ExclusionZoneListResponse,
    ExclusionZoneResponse,
    ExclusionZoneUpdate,
    SpatialQueryRequest,
    SpatialQueryResponse,
)

router = APIRouter()


def verify_project_access(db: Session, project_id: UUID, user_id: UUID) -> None:
    """Verify user has access to the project."""
    project = crud_project.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )


@router.get("/{project_id}/zones", response_model=ExclusionZoneListResponse)
def list_exclusion_zones(
    project_id: UUID,
    active_only: bool = True,
    zone_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all exclusion zones for a project."""
    verify_project_access(db, project_id, current_user.id)

    zones = crud_exclusion_zone.get_by_project(
        db, project_id, active_only=active_only, zone_type=zone_type
    )

    return ExclusionZoneListResponse(
        zones=[
            ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))
            for zone in zones
        ],
        total=len(zones),
    )


@router.post(
    "/{project_id}/zones",
    response_model=ExclusionZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exclusion_zone(
    project_id: UUID,
    zone_data: ExclusionZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new exclusion zone (drawn on map)."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.create(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        name=zone_data.name,
        zone_type=zone_data.zone_type,
        geometry=zone_data.geometry,
        source="drawn",
        description=zone_data.description,
        buffer_distance=zone_data.buffer_distance,
        fill_color=zone_data.fill_color,
        stroke_color=zone_data.stroke_color,
        fill_opacity=zone_data.fill_opacity,
    )

    return ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))


@router.post(
    "/{project_id}/zones/import",
    response_model=ExclusionZoneImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_exclusion_zones(
    project_id: UUID,
    import_data: ExclusionZoneImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import exclusion zones from an uploaded KML/KMZ file."""
    verify_project_access(db, project_id, current_user.id)

    # Get the uploaded file
    uploaded_file = crud_uploaded_file.get(db, import_data.source_file_id)
    if not uploaded_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found",
        )

    if uploaded_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    # Read and parse the file
    try:
        with open(uploaded_file.file_path, "rb") as f:
            file_content = f.read()

        # Parse KML/KMZ content
        from app.services.file_validation import validate_file

        validation_result = validate_file(
            Path(uploaded_file.file_path),
            file_content,
        )

        if not validation_result.is_valid or not validation_result.geometry_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file: {validation_result.error_message}",
            )

        geometry_result = validation_result.geometry_result

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}",
        )

    # Create exclusion zone from geometry
    name_prefix = (
        import_data.name_prefix or uploaded_file.extracted_name or "Imported Zone"
    )
    geometry = geometry_result.geometry

    # Handle multi-geometry by creating separate zones
    zones_created = []
    geometries_to_process = []

    if geometry.geom_type.startswith("Multi"):
        # Split multi-geometry into individual geometries
        for i, geom in enumerate(geometry.geoms):
            geometries_to_process.append((f"{name_prefix} {i + 1}", geom))
    else:
        geometries_to_process.append((name_prefix, geometry))

    for zone_name, geom in geometries_to_process:
        zone = crud_exclusion_zone.create(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            name=zone_name,
            zone_type=import_data.zone_type,
            geometry=geom.__geo_interface__,
            source="imported",
            description=geometry_result.description,
            buffer_distance=import_data.buffer_distance,
            source_file_id=import_data.source_file_id,
        )
        zones_created.append(zone)

    return ExclusionZoneImportResponse(
        zones_created=len(zones_created),
        zones=[
            ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))
            for zone in zones_created
        ],
        message=f"Successfully imported {len(zones_created)} zone(s) from file",
    )


@router.get("/{project_id}/zones/{zone_id}", response_model=ExclusionZoneResponse)
def get_exclusion_zone(
    project_id: UUID,
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific exclusion zone."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.get(db, zone_id)
    if not zone or zone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion zone not found",
        )

    return ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))


@router.patch("/{project_id}/zones/{zone_id}", response_model=ExclusionZoneResponse)
def update_exclusion_zone(
    project_id: UUID,
    zone_id: UUID,
    zone_data: ExclusionZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an exclusion zone."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.get(db, zone_id)
    if not zone or zone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion zone not found",
        )

    zone = crud_exclusion_zone.update(
        db=db,
        db_obj=zone,
        name=zone_data.name,
        description=zone_data.description,
        zone_type=zone_data.zone_type,
        buffer_distance=zone_data.buffer_distance,
        is_active=zone_data.is_active,
        fill_color=zone_data.fill_color,
        stroke_color=zone_data.stroke_color,
        fill_opacity=zone_data.fill_opacity,
    )

    return ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))


@router.post(
    "/{project_id}/zones/{zone_id}/buffer", response_model=ExclusionZoneResponse
)
def apply_buffer_to_zone(
    project_id: UUID,
    zone_id: UUID,
    buffer_data: BufferApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a buffer distance to an exclusion zone."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.get(db, zone_id)
    if not zone or zone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion zone not found",
        )

    zone = crud_exclusion_zone.apply_buffer(db, zone, buffer_data.buffer_distance)

    return ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))


@router.delete(
    "/{project_id}/zones/{zone_id}/buffer", response_model=ExclusionZoneResponse
)
def remove_buffer_from_zone(
    project_id: UUID,
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove buffer from an exclusion zone."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.get(db, zone_id)
    if not zone or zone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion zone not found",
        )

    zone = crud_exclusion_zone.remove_buffer(db, zone)

    return ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))


@router.delete("/{project_id}/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exclusion_zone(
    project_id: UUID,
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an exclusion zone."""
    verify_project_access(db, project_id, current_user.id)

    zone = crud_exclusion_zone.get(db, zone_id)
    if not zone or zone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion zone not found",
        )

    crud_exclusion_zone.delete(db, zone_id)


@router.post(
    "/{project_id}/zones/check-intersection", response_model=SpatialQueryResponse
)
def check_zone_intersection(
    project_id: UUID,
    query_data: SpatialQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a geometry intersects with any exclusion zones."""
    verify_project_access(db, project_id, current_user.id)

    intersecting_zones = crud_exclusion_zone.find_intersecting(
        db, project_id, query_data.geometry
    )

    return SpatialQueryResponse(
        intersects=len(intersecting_zones) > 0,
        intersecting_zones=[
            ExclusionZoneResponse(**crud_exclusion_zone.to_response_dict(zone))
            for zone in intersecting_zones
        ],
        total_intersecting=len(intersecting_zones),
    )
