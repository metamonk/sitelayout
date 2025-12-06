"""Pydantic schemas for road network generation."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RoadNetworkConfigBase(BaseModel):
    """Base configuration for road network generation."""

    name: str = Field(..., description="Name for this road network configuration")
    description: Optional[str] = Field(None, description="Optional description")

    # Road specifications
    road_width: float = Field(
        6.0, gt=0, le=20, description="Road width in meters (6-8m typical)"
    )
    max_grade: float = Field(
        12.0,
        gt=0,
        le=30,
        description="Maximum grade percentage (12% for construction vehicles)",
    )
    min_curve_radius: float = Field(
        15.0, gt=0, description="Minimum turning radius in meters"
    )

    # Grid configuration
    grid_resolution: float = Field(
        5.0, gt=0, le=50, description="Pathfinding grid cell size in meters"
    )

    # Optimization settings
    optimization_criteria: str = Field(
        "balanced",
        description="Optimization: minimal_length, minimal_earthwork, balanced",
    )

    # Buffer distances
    exclusion_buffer: float = Field(
        5.0, ge=0, description="Buffer distance from exclusion zones in meters"
    )

    # Advanced settings
    advanced_settings: Optional[dict[str, Any]] = Field(
        None,
        description="Advanced settings like prefer_contours, etc.",
    )


class RoadNetworkCreate(RoadNetworkConfigBase):
    """Schema for creating a road network generation request."""

    terrain_analysis_id: Optional[UUID] = Field(
        None, description="UUID of terrain analysis to use for elevation/slope data"
    )
    asset_placement_id: Optional[UUID] = Field(
        None, description="UUID of asset placement to connect with roads"
    )
    entry_point: Optional[dict[str, Any]] = Field(
        None,
        description="GeoJSON Point for site entry (uses project entry_point)",
    )


class RoadNetworkUpdate(BaseModel):
    """Schema for updating a road network (e.g., manual adjustments)."""

    name: Optional[str] = None
    description: Optional[str] = None
    road_details: Optional[dict[str, Any]] = Field(
        None, description="Updated road details with manual adjustments"
    )


class RoadSegmentInfo(BaseModel):
    """Information about a single road segment."""

    id: int = Field(..., description="Segment ID in this network")
    from_node: int = Field(
        ..., description="Starting node ID (asset ID or intersection)"
    )
    to_node: int = Field(..., description="Ending node ID (asset ID or intersection)")
    length_m: float = Field(..., description="Segment length in meters")
    avg_grade: float = Field(..., description="Average grade percentage")
    max_grade: float = Field(..., description="Maximum grade percentage along segment")
    cut_volume: Optional[float] = Field(None, description="Cut volume in cubic meters")
    fill_volume: Optional[float] = Field(
        None, description="Fill volume in cubic meters"
    )
    coordinates: list[list[float]] = Field(
        ..., description="Line coordinates as [[lon, lat, elev], ...]"
    )


class IntersectionInfo(BaseModel):
    """Information about a road intersection."""

    id: int = Field(..., description="Intersection ID")
    position: list[float] = Field(
        ..., description="Position as [longitude, latitude]", min_length=2, max_length=2
    )
    connected_segments: list[int] = Field(
        ..., description="IDs of segments meeting at this intersection"
    )
    elevation: Optional[float] = Field(
        None, description="Elevation at intersection in meters"
    )


class RoadNetworkStatistics(BaseModel):
    """Statistics about the road network results."""

    total_road_length: float = Field(..., description="Total road length in meters")
    total_segments: int = Field(..., description="Number of road segments")
    total_intersections: int = Field(..., description="Number of intersections")

    # Grade statistics
    avg_grade: float = Field(..., description="Average grade percentage")
    max_grade_actual: float = Field(..., description="Actual maximum grade in network")
    grade_compliant: bool = Field(..., description="All grades within constraint")

    # Earthwork
    total_cut_volume: Optional[float] = Field(
        None, description="Total cut volume in cubic meters"
    )
    total_fill_volume: Optional[float] = Field(
        None, description="Total fill volume in cubic meters"
    )
    net_earthwork_volume: Optional[float] = Field(
        None, description="Net earthwork (cut - fill)"
    )

    # Connectivity
    assets_connected: int = Field(..., description="Number of assets connected")
    connectivity_rate: float = Field(..., description="Connectivity rate percentage")


class RoadNetworkResponse(BaseModel):
    """Schema for road network response."""

    id: UUID
    project_id: UUID
    user_id: UUID
    terrain_analysis_id: Optional[UUID] = None
    asset_placement_id: Optional[UUID] = None

    # Metadata
    name: str
    description: Optional[str] = None

    # Status
    status: str
    progress_percent: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None

    # Configuration (echo back what was requested)
    road_width: float
    max_grade: float
    min_curve_radius: float
    grid_resolution: float
    optimization_criteria: str
    exclusion_buffer: float
    advanced_settings: Optional[dict[str, Any]] = None

    # Entry point
    entry_point: Optional[dict[str, Any]] = None  # GeoJSON Point

    # Results
    road_centerlines: Optional[dict[str, Any]] = None  # GeoJSON MultiLineString
    road_polygons: Optional[dict[str, Any]] = None  # GeoJSON MultiPolygon
    road_details: Optional[dict[str, Any]] = None  # Detailed segments and intersections

    # Statistics
    statistics: Optional[RoadNetworkStatistics] = None

    # Processing metadata
    processing_time_seconds: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    algorithm_iterations: Optional[int] = None
    pathfinding_algorithm: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoadNetworkListResponse(BaseModel):
    """Schema for list of road networks."""

    road_networks: list[RoadNetworkResponse]
    total: int


class RoadSegmentAdjustment(BaseModel):
    """Schema for manually adjusting a road segment."""

    segment_id: int = Field(..., description="ID of the segment to adjust")
    new_coordinates: list[list[float]] = Field(
        ..., description="New coordinates as [[lon, lat], ...]"
    )


class RoadNetworkAdjustmentRequest(BaseModel):
    """Schema for batch road segment adjustments."""

    adjustments: list[RoadSegmentAdjustment] = Field(
        ..., description="List of segment adjustments to apply"
    )
