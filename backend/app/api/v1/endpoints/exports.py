"""API endpoints for export and reporting functionality."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.crud.asset_placement import asset_placement as placement_crud
from app.crud.exclusion_zone import exclusion_zone as zone_crud
from app.crud.project import project as project_crud
from app.crud.road_network import road_network as road_crud
from app.crud.terrain_analysis import terrain_analysis as terrain_crud
from app.db.base import get_db
from app.models.user import User
from app.schemas.export import (
    AvailableFormatsResponse,
    DXFExportRequest,
    ExportLayer,
    KMZExportRequest,
    PDFReportRequest,
)
from app.services.export_service import ExportService

router = APIRouter()
export_service = ExportService()


def verify_project_access(
    db: Session,
    project_id: UUID,
    user: User,
):
    """Verify user has access to the project and return project data."""
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
    return project


def get_project_data(db: Session, project_id: UUID):
    """Gather all project data for export."""
    project = project_crud.get(db, project_id=project_id)

    # Get terrain analysis
    terrain_analyses = terrain_crud.get_by_project(db, project_id=project_id)
    terrain_data = None
    if terrain_analyses:
        terrain = terrain_analyses[0]  # Use the first/latest
        terrain_data = terrain_crud.to_response_dict(terrain)

    # Get asset placements
    placements = placement_crud.get_by_project(db, project_id=project_id)
    placements_data = [placement_crud.to_response_dict(p) for p in placements]

    # Get road networks
    roads = road_crud.get_by_project(db, project_id=project_id)
    roads_data = [road_crud.to_response_dict(r) for r in roads]

    # Get exclusion zones
    zones = zone_crud.get_by_project(db, project_id=project_id)
    zones_data = [zone_crud.to_response_dict(z) for z in zones]

    return {
        "project": project_crud.to_response_dict(project) if project else {},
        "terrain": terrain_data,
        "placements": placements_data,
        "roads": roads_data,
        "zones": zones_data,
    }


@router.get(
    "/projects/{project_id}/exports/formats",
    response_model=AvailableFormatsResponse,
)
def get_available_formats(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get available export formats and their descriptions.
    """
    verify_project_access(db, project_id, current_user)

    formats = [
        {
            "format": "pdf",
            "name": "PDF Report",
            "description": "Comprehensive project report with all data sections",
            "content_type": "application/pdf",
            "supports_layers": False,
        },
        {
            "format": "geojson",
            "name": "GeoJSON",
            "description": "Standard geospatial format for web mapping",
            "content_type": "application/geo+json",
            "supports_layers": True,
            "layers": ["assets", "roads", "zones", "all"],
        },
        {
            "format": "kmz",
            "name": "KMZ (Google Earth)",
            "description": "Compressed KML for Google Earth with 3D support",
            "content_type": "application/vnd.google-earth.kmz",
            "supports_layers": True,
        },
        {
            "format": "shapefile",
            "name": "Shapefile",
            "description": "ESRI Shapefile format for GIS software",
            "content_type": "application/zip",
            "supports_layers": True,
            "layers": ["assets", "roads", "zones"],
        },
        {
            "format": "csv",
            "name": "CSV",
            "description": "Comma-separated values for spreadsheets",
            "content_type": "text/csv",
            "data_types": ["assets", "roads", "summary"],
        },
        {
            "format": "dxf",
            "name": "DXF (AutoCAD)",
            "description": "Drawing Exchange Format for CAD software",
            "content_type": "application/dxf",
            "supports_layers": True,
        },
    ]

    return {"formats": formats}


@router.post(
    "/projects/{project_id}/exports/pdf",
    response_class=Response,
)
def export_pdf_report(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Optional[PDFReportRequest] = None,
):
    """
    Generate and download a PDF project report.

    The report includes:
    - Project overview and metadata
    - Terrain analysis statistics (if available)
    - Asset placement details and metrics
    - Road network summary
    - Exclusion zone listing
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)

    # Apply filters based on request
    if request:
        if not request.include_terrain:
            data["terrain"] = None
        if not request.include_assets:
            data["placements"] = None
        if not request.include_roads:
            data["roads"] = None
        if not request.include_zones:
            data["zones"] = None

    result = export_service.export_pdf_report(
        project=data["project"],
        terrain_analysis=data["terrain"],
        asset_placements=data["placements"],
        road_networks=data["roads"],
        exclusion_zones=data["zones"],
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "PDF generation failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post(
    "/projects/{project_id}/exports/geojson",
    response_class=Response,
)
def export_geojson(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    layer: ExportLayer = Query(ExportLayer.ALL, description="Layer to export"),
):
    """
    Export project data to GeoJSON format.

    Supports exporting individual layers (assets, roads, zones) or all layers combined.
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)
    project_name = data["project"].get("name", "project").replace(" ", "_").lower()

    if layer == ExportLayer.ALL:
        result = export_service.export_geojson_combined(
            placements=data["placements"],
            road_networks=data["roads"],
            exclusion_zones=data["zones"],
            project_name=project_name,
        )
    elif layer == ExportLayer.ASSETS:
        result = export_service.export_geojson(
            "assets", data["placements"], project_name
        )
    elif layer == ExportLayer.ROADS:
        result = export_service.export_geojson("roads", data["roads"], project_name)
    elif layer == ExportLayer.ZONES:
        result = export_service.export_geojson("zones", data["zones"], project_name)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid layer: {layer}",
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "GeoJSON export failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post(
    "/projects/{project_id}/exports/kmz",
    response_class=Response,
)
def export_kmz(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Optional[KMZExportRequest] = None,
):
    """
    Export project data to KMZ format for Google Earth.

    KMZ files include:
    - Assets as placemarks with icons
    - Roads as styled polylines
    - Exclusion zones as polygons with transparency
    - 3D elevation data when available
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)
    project_name = data["project"].get("name", "project").replace(" ", "_").lower()

    placements = data["placements"] if (not request or request.include_assets) else None
    roads = data["roads"] if (not request or request.include_roads) else None
    zones = data["zones"] if (not request or request.include_zones) else None

    result = export_service.export_kmz(
        project_name=project_name,
        placements=placements,
        road_networks=roads,
        exclusion_zones=zones,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "KMZ export failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post(
    "/projects/{project_id}/exports/shapefile",
    response_class=Response,
)
def export_shapefile(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    layer: ExportLayer = Query(
        ..., description="Layer to export (assets, roads, or zones)"
    ),
):
    """
    Export project data to ESRI Shapefile format.

    Returns a ZIP archive containing all required Shapefile components
    (.shp, .shx, .dbf, .prj, .cpg).

    Note: Shapefiles export one geometry type at a time, so you must specify
    which layer to export (assets=points, roads=lines, zones=polygons).
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)
    project_name = data["project"].get("name", "project").replace(" ", "_").lower()

    if layer == ExportLayer.ALL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shapefile export requires a specific layer",
        )
    elif layer == ExportLayer.ASSETS:
        result = export_service.export_shapefile(
            "assets", data["placements"], project_name
        )
    elif layer == ExportLayer.ROADS:
        result = export_service.export_shapefile("roads", data["roads"], project_name)
    elif layer == ExportLayer.ZONES:
        result = export_service.export_shapefile("zones", data["zones"], project_name)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid layer: {layer}",
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "Shapefile export failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post(
    "/projects/{project_id}/exports/csv",
    response_class=Response,
)
def export_csv(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    data_type: str = Query(
        ..., description="Data type to export: 'assets', 'roads', or 'summary'"
    ),
):
    """
    Export project data to CSV format.

    Available data types:
    - assets: List of placed assets with coordinates and properties
    - roads: Road segment details with lengths and grades
    - summary: Project overview with terrain, placement, and road statistics
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)
    project_name = data["project"].get("name", "project").replace(" ", "_").lower()

    if data_type == "assets":
        result = export_service.export_csv("assets", data["placements"], project_name)
    elif data_type == "roads":
        result = export_service.export_csv("roads", data["roads"], project_name)
    elif data_type == "summary":
        result = export_service.export_csv(
            "summary",
            data["project"],
            project_name,
            terrain_analysis=data["terrain"],
            asset_placements=data["placements"],
            road_networks=data["roads"],
            exclusion_zones=data["zones"],
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data type: {data_type}. Use assets/roads/summary",
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "CSV export failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@router.post(
    "/projects/{project_id}/exports/dxf",
    response_class=Response,
)
def export_dxf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Optional[DXFExportRequest] = None,
):
    """
    Export project data to DXF format for CAD software.

    The DXF file includes separate layers for:
    - ASSETS: Asset footprints as rectangles
    - ROADS: Road centerlines as polylines
    - EXCLUSION_ZONES: Zone boundaries as polygons
    - LABELS: Text labels for features

    Coordinates are scaled from WGS84 degrees to meters (approximate).
    """
    verify_project_access(db, project_id, current_user)
    data = get_project_data(db, project_id)
    project_name = data["project"].get("name", "project").replace(" ", "_").lower()

    placements = data["placements"] if (not request or request.include_assets) else None
    roads = data["roads"] if (not request or request.include_roads) else None
    zones = data["zones"] if (not request or request.include_zones) else None

    result = export_service.export_dxf(
        project_name=project_name,
        placements=placements,
        road_networks=roads,
        exclusion_zones=zones,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "DXF export failed",
        )

    return Response(
        content=result.file_content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
