"""Pydantic schemas for cut/fill volume estimation."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AssetVolumeDetail(BaseModel):
    """Volume details for a single asset."""

    asset_id: int
    position: dict[str, float] = Field(
        ..., description="Asset position as {longitude, latitude}"
    )
    foundation_type: str
    cut_volume_m3: float = Field(..., description="Cut volume in cubic meters")
    fill_volume_m3: float = Field(..., description="Fill volume in cubic meters")
    net_volume_m3: float = Field(
        ..., description="Net volume (positive = cut, negative = fill)"
    )
    footprint_area_m2: float = Field(..., description="Asset footprint in sq meters")
    max_cut_depth_m: float = Field(..., description="Maximum cut depth in meters")
    max_fill_depth_m: float = Field(..., description="Maximum fill depth in meters")


class RoadSegmentVolumeDetail(BaseModel):
    """Volume details for a road segment."""

    segment_id: int
    from_asset: int
    to_asset: int
    length_m: float = Field(..., description="Road segment length in meters")
    area_m2: float = Field(..., description="Road segment area in square meters")
    cut_volume_m3: float = Field(..., description="Cut volume in cubic meters")
    fill_volume_m3: float = Field(..., description="Fill volume in cubic meters")
    net_volume_m3: float = Field(..., description="Net volume in cubic meters")
    avg_cut_depth_m: float = Field(..., description="Average cut depth in meters")
    avg_fill_depth_m: float = Field(..., description="Average fill depth in meters")


class VolumeEstimationCreate(BaseModel):
    """Schema for creating a volume estimation request."""

    terrain_analysis_id: Optional[UUID] = Field(
        None, description="UUID of terrain analysis to use for DEM data"
    )
    asset_placement_id: Optional[UUID] = Field(
        None, description="UUID of asset placement to calculate volumes for"
    )
    road_network_id: Optional[UUID] = Field(
        None, description="UUID of road network to calculate volumes for"
    )
    grid_resolution: float = Field(
        2.0,
        ge=1.0,
        le=10.0,
        description="Grid cell size in meters (1-10m)",
    )
    default_foundation_type: str = Field(
        "pad",
        description="Default foundation type for assets (pad, pier, strip, raft)",
    )
    road_width: float = Field(6.0, ge=3.0, le=20.0, description="Road width in meters")
    include_visualization: bool = Field(
        True, description="Whether to generate 3D visualization data"
    )


class VolumeEstimationSummary(BaseModel):
    """Summary of volume estimation results."""

    total_cut_volume_m3: float
    total_fill_volume_m3: float
    total_net_volume_m3: float
    cut_fill_ratio: float = Field(
        ..., description="Ratio of cut to fill (1.0 = balanced)"
    )
    balance_status: str = Field(
        ..., description="Balance status: Balanced, Excess Cut, or Excess Fill"
    )


class AssetVolumeSummary(BaseModel):
    """Summary of asset volumes."""

    total_assets: int
    total_cut_volume_m3: float
    total_fill_volume_m3: float
    total_net_volume_m3: float


class RoadVolumeSummary(BaseModel):
    """Summary of road volumes."""

    total_segments: int
    total_cut_volume_m3: float
    total_fill_volume_m3: float
    total_net_volume_m3: float


class ProcessingMetadata(BaseModel):
    """Processing metadata for volume estimation."""

    dem_resolution_m: Optional[float] = None
    grid_cell_size_m: float
    total_cells_analyzed: int
    processing_time_seconds: Optional[float] = None
    memory_peak_mb: Optional[float] = None


class VolumeEstimationResponse(BaseModel):
    """Schema for volume estimation response."""

    id: UUID
    project_id: UUID
    terrain_analysis_id: Optional[UUID] = None
    asset_placement_id: Optional[UUID] = None
    road_network_id: Optional[UUID] = None

    # Status
    status: str
    progress_percent: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None

    # Configuration
    grid_resolution: float
    default_foundation_type: str
    road_width: float

    # Summaries
    summary: Optional[VolumeEstimationSummary] = None
    asset_summary: Optional[AssetVolumeSummary] = None
    road_summary: Optional[RoadVolumeSummary] = None

    # Analysis bounds as GeoJSON
    analysis_bounds: Optional[dict[str, Any]] = None

    # Processing metadata
    processing_metadata: Optional[ProcessingMetadata] = None

    # Flags for available data
    has_asset_details: bool = False
    has_road_details: bool = False
    has_visualization_data: bool = False
    has_report: bool = False

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VolumeEstimationDetailResponse(VolumeEstimationResponse):
    """Extended response with full details."""

    asset_volumes: Optional[list[AssetVolumeDetail]] = None
    road_volumes: Optional[list[RoadSegmentVolumeDetail]] = None
    visualization_data: Optional[dict[str, Any]] = None


class VolumeEstimationListResponse(BaseModel):
    """Schema for list of volume estimations."""

    estimations: list[VolumeEstimationResponse]
    total: int


class VolumetricReportResponse(BaseModel):
    """Schema for volumetric report."""

    project_name: str
    generated_at: str
    summary: VolumeEstimationSummary
    asset_breakdown: dict[str, Any]
    road_breakdown: dict[str, Any]
    processing_metadata: ProcessingMetadata


class VisualizationDataResponse(BaseModel):
    """Schema for 3D visualization data."""

    bounds: dict[str, float] = Field(
        ..., description="Bounding box {minx, miny, maxx, maxy}"
    )
    grid_resolution: float
    grid_width: int
    grid_height: int
    assets: list[dict[str, Any]]
    roads: list[dict[str, Any]]
