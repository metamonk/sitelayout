"""Pydantic schemas for asset placement."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlacementConfigBase(BaseModel):
    """Base configuration for asset placement."""

    name: str = Field(..., description="Name for this placement configuration")
    description: Optional[str] = Field(None, description="Optional description")

    # Asset specifications
    asset_width: float = Field(..., gt=0, description="Width of asset in meters")
    asset_length: float = Field(..., gt=0, description="Length of asset in meters")
    asset_count: int = Field(
        ..., gt=0, le=500, description="Number of assets to place (max 500)"
    )

    # Grid configuration
    grid_resolution: float = Field(
        5.0, gt=0, le=50, description="Grid cell size in meters"
    )

    # Constraints
    min_spacing: float = Field(
        10.0, ge=0, description="Minimum spacing between assets in meters"
    )
    max_slope: float = Field(
        5.0, ge=0, le=45, description="Maximum allowed slope in degrees"
    )

    # Optimization settings
    optimization_criteria: str = Field(
        "balanced",
        description="Optimization: minimize_cut_fill, maximize_flat_areas, etc.",
    )

    # Advanced settings
    advanced_settings: Optional[dict[str, Any]] = Field(
        None,
        description="Advanced settings like buffer_from_exclusion_zones, etc.",
    )


class AssetPlacementCreate(PlacementConfigBase):
    """Schema for creating an asset placement request."""

    terrain_analysis_id: Optional[UUID] = Field(
        None, description="UUID of terrain analysis to use for elevation/slope data"
    )
    placement_area: Optional[dict[str, Any]] = Field(
        None,
        description="GeoJSON polygon for placement area (uses project boundary)",
    )


class AssetPlacementUpdate(BaseModel):
    """Schema for updating an asset placement (e.g., manually adjusting results)."""

    name: Optional[str] = None
    description: Optional[str] = None
    placement_details: Optional[dict[str, Any]] = Field(
        None, description="Updated placement details with manual adjustments"
    )


class PlacedAssetInfo(BaseModel):
    """Information about a single placed asset."""

    id: int = Field(..., description="Asset ID in this placement")
    position: list[float] = Field(
        ..., description="Position as [longitude, latitude]", min_length=2, max_length=2
    )
    elevation: Optional[float] = Field(
        None, description="Elevation at asset location in meters"
    )
    slope: Optional[float] = Field(
        None, description="Slope at asset location in degrees"
    )
    rotation: Optional[float] = Field(None, description="Asset rotation in degrees")
    score: Optional[float] = Field(
        None, description="Optimization score for this location"
    )


class PlacementStatistics(BaseModel):
    """Statistics about the placement results."""

    assets_placed: int
    assets_requested: int
    placement_success_rate: float
    grid_cells_total: Optional[int] = None
    grid_cells_valid: Optional[int] = None
    grid_cells_excluded: Optional[int] = None
    avg_slope: Optional[float] = None
    avg_inter_asset_distance: Optional[float] = None
    total_cut_fill_volume: Optional[float] = None


class AssetPlacementResponse(BaseModel):
    """Schema for asset placement response."""

    id: UUID
    project_id: UUID
    user_id: UUID
    terrain_analysis_id: Optional[UUID] = None

    # Metadata
    name: str
    description: Optional[str] = None

    # Status
    status: str
    progress_percent: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None

    # Configuration (echo back what was requested)
    asset_width: float
    asset_length: float
    asset_count: int
    grid_resolution: float
    min_spacing: float
    max_slope: float
    optimization_criteria: str
    advanced_settings: Optional[dict[str, Any]] = None

    # Results
    placement_area: Optional[dict[str, Any]] = None  # GeoJSON
    placed_assets: Optional[dict[str, Any]] = None  # GeoJSON MultiPoint
    placement_details: Optional[dict[str, Any]] = (
        None  # Detailed array of placed assets
    )

    # Statistics
    statistics: Optional[PlacementStatistics] = None

    # Processing metadata
    processing_time_seconds: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    algorithm_iterations: Optional[int] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssetPlacementListResponse(BaseModel):
    """Schema for list of asset placements."""

    placements: list[AssetPlacementResponse]
    total: int


class AssetAdjustment(BaseModel):
    """Schema for manually adjusting a placed asset."""

    asset_id: int = Field(..., description="ID of the asset to adjust")
    new_position: list[float] = Field(
        ...,
        description="New position as [longitude, latitude]",
        min_length=2,
        max_length=2,
    )
    new_rotation: Optional[float] = Field(None, description="New rotation in degrees")


class AssetAdjustmentRequest(BaseModel):
    """Schema for batch asset adjustments."""

    adjustments: list[AssetAdjustment] = Field(
        ..., description="List of asset adjustments to apply"
    )
