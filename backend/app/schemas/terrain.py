"""Pydantic schemas for terrain analysis."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ElevationStatsResponse(BaseModel):
    """Elevation statistics."""

    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    nodata_count: int = 0
    valid_count: int = 0


class SlopeStatsResponse(BaseModel):
    """Slope analysis statistics."""

    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    classification: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage of area in each slope class",
    )


class AspectStatsResponse(BaseModel):
    """Aspect analysis statistics."""

    distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage of area facing each direction",
    )


class TerrainAnalysisCreate(BaseModel):
    """Schema for creating a terrain analysis request."""

    source_file_id: Optional[UUID] = Field(
        None, description="UUID of uploaded DEM file to analyze"
    )
    dem_url: Optional[str] = Field(
        None, description="URL to external DEM source (alternative to file upload)"
    )
    bounds: Optional[list[float]] = Field(
        None,
        description="Bounding box [minx, miny, maxx, maxy] to clip analysis",
        min_length=4,
        max_length=4,
    )


class TerrainAnalysisResponse(BaseModel):
    """Schema for terrain analysis response."""

    id: UUID
    project_id: UUID
    source_file_id: Optional[UUID] = None

    # Status
    status: str
    progress_percent: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None

    # DEM info
    dem_source: Optional[str] = None
    dem_resolution: Optional[float] = None
    dem_crs: Optional[str] = None
    analysis_bounds: Optional[dict[str, Any]] = None

    # Statistics
    elevation_stats: Optional[ElevationStatsResponse] = None
    slope_stats: Optional[SlopeStatsResponse] = None
    aspect_stats: Optional[AspectStatsResponse] = None

    # Generated raster URLs (not paths for security)
    slope_raster_available: bool = False
    aspect_raster_available: bool = False
    hillshade_raster_available: bool = False

    # Processing metadata
    processing_time_seconds: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    is_cached: bool = False

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TerrainAnalysisListResponse(BaseModel):
    """Schema for list of terrain analyses."""

    analyses: list[TerrainAnalysisResponse]
    total: int


class TerrainProfileRequest(BaseModel):
    """Request for terrain profile along a line."""

    start_point: list[float] = Field(
        ..., description="Start point [longitude, latitude]", min_length=2, max_length=2
    )
    end_point: list[float] = Field(
        ..., description="End point [longitude, latitude]", min_length=2, max_length=2
    )
    num_samples: int = Field(100, ge=10, le=1000, description="Number of sample points")


class TerrainProfileResponse(BaseModel):
    """Response for terrain profile."""

    points: list[dict[str, float]]
    elevations: list[Optional[float]]
    distances: list[float]
    total_distance: float
    elevation_gain: float
    elevation_loss: float


class ElevationAtPointsRequest(BaseModel):
    """Request for elevation at specific points."""

    points: list[list[float]] = Field(
        ...,
        description="List of [longitude, latitude] points",
        min_length=1,
        max_length=1000,
    )


class ElevationAtPointsResponse(BaseModel):
    """Response for elevation at points."""

    elevations: list[Optional[float]]
