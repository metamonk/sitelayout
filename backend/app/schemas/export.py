"""Schemas for export and reporting functionality."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    """Supported export formats."""

    PDF = "pdf"
    GEOJSON = "geojson"
    KMZ = "kmz"
    SHAPEFILE = "shapefile"
    CSV = "csv"
    DXF = "dxf"


class ExportLayer(str, Enum):
    """Layers available for export."""

    ASSETS = "assets"
    ROADS = "roads"
    ZONES = "zones"
    ALL = "all"


class ExportRequest(BaseModel):
    """Base request for export operations."""

    format: ExportFormat
    layers: list[ExportLayer] = Field(default=[ExportLayer.ALL])
    include_terrain: bool = Field(
        default=True, description="Include terrain analysis in report"
    )


class PDFReportRequest(BaseModel):
    """Request for PDF report generation."""

    include_terrain: bool = Field(
        default=True, description="Include terrain analysis section"
    )
    include_assets: bool = Field(
        default=True, description="Include asset placement section"
    )
    include_roads: bool = Field(
        default=True, description="Include road network section"
    )
    include_zones: bool = Field(
        default=True, description="Include exclusion zones section"
    )


class GeoJSONExportRequest(BaseModel):
    """Request for GeoJSON export."""

    layer: ExportLayer = Field(default=ExportLayer.ALL, description="Layer to export")
    include_properties: bool = Field(
        default=True, description="Include feature properties"
    )


class KMZExportRequest(BaseModel):
    """Request for KMZ export."""

    include_assets: bool = Field(default=True)
    include_roads: bool = Field(default=True)
    include_zones: bool = Field(default=True)
    use_3d: bool = Field(default=True, description="Use 3D coordinates if available")


class ShapefileExportRequest(BaseModel):
    """Request for Shapefile export."""

    layer: ExportLayer = Field(description="Layer to export (assets, roads, or zones)")


class CSVExportRequest(BaseModel):
    """Request for CSV export."""

    data_type: str = Field(
        description="Type of data to export: 'assets', 'roads', or 'summary'"
    )


class DXFExportRequest(BaseModel):
    """Request for DXF export."""

    include_assets: bool = Field(default=True)
    include_roads: bool = Field(default=True)
    include_zones: bool = Field(default=True)
    scale_factor: float = Field(
        default=111000.0,
        description="Scale factor for coordinate conversion (degrees to meters)",
    )


class ExportMetadata(BaseModel):
    """Metadata about an export."""

    format: ExportFormat
    filename: str
    content_type: str
    file_size: Optional[int] = None
    feature_count: Optional[int] = None
    generated_at: datetime
    project_id: UUID
    project_name: str


class ExportResponse(BaseModel):
    """Response for export operations."""

    success: bool
    message: str
    metadata: Optional[ExportMetadata] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class ExportHistoryItem(BaseModel):
    """Record of a past export."""

    id: UUID
    project_id: UUID
    format: ExportFormat
    layers: list[str]
    filename: str
    file_size: int
    created_at: datetime
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None


class ExportHistoryResponse(BaseModel):
    """Response listing export history."""

    exports: list[ExportHistoryItem]
    total: int


class AvailableFormatsResponse(BaseModel):
    """Response listing available export formats."""

    formats: list[dict[str, Any]]


# Convenience type for bulk export requests
class BulkExportRequest(BaseModel):
    """Request for exporting multiple formats at once."""

    formats: list[ExportFormat]
    layers: list[ExportLayer] = Field(default=[ExportLayer.ALL])
    include_terrain: bool = Field(default=True)


class BulkExportResponse(BaseModel):
    """Response for bulk export operations."""

    success: bool
    exports: list[ExportResponse]
    archive_url: Optional[str] = Field(
        default=None, description="URL to download all exports as a single ZIP archive"
    )
