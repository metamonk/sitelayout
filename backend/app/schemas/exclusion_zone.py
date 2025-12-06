from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExclusionZoneBase(BaseModel):
    """Base schema for exclusion zone."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    zone_type: str = Field(
        ..., pattern="^(wetland|easement|stream_buffer|setback|custom)$"
    )
    buffer_distance: Optional[float] = Field(None, ge=0, le=10000)
    fill_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    stroke_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    fill_opacity: Optional[float] = Field(None, ge=0, le=1)


class ExclusionZoneCreate(ExclusionZoneBase):
    """Schema for creating an exclusion zone."""

    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry")

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate GeoJSON geometry structure."""
        if not isinstance(v, dict):
            raise ValueError("Geometry must be a dictionary")
        if "type" not in v:
            raise ValueError("Geometry must have a 'type' field")
        if "coordinates" not in v:
            raise ValueError("Geometry must have a 'coordinates' field")

        valid_types = [
            "Polygon",
            "MultiPolygon",
            "Point",
            "LineString",
            "MultiPoint",
            "MultiLineString",
        ]
        if v["type"] not in valid_types:
            raise ValueError(f"Geometry type must be one of: {valid_types}")

        return v


class ExclusionZoneUpdate(BaseModel):
    """Schema for updating an exclusion zone."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    zone_type: Optional[str] = Field(
        None, pattern="^(wetland|easement|stream_buffer|setback|custom)$"
    )
    buffer_distance: Optional[float] = Field(None, ge=0, le=10000)
    is_active: Optional[bool] = None
    fill_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    stroke_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    fill_opacity: Optional[float] = Field(None, ge=0, le=1)


class ExclusionZoneResponse(BaseModel):
    """Response schema for exclusion zone."""

    id: UUID
    project_id: UUID
    user_id: UUID
    name: str
    description: Optional[str] = None
    zone_type: str
    source: str
    geometry: dict[str, Any]
    geometry_type: str
    buffer_distance: Optional[float] = None
    buffer_applied: bool
    buffered_geometry: Optional[dict[str, Any]] = None
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    fill_opacity: Optional[float] = None
    area_sqm: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExclusionZoneListResponse(BaseModel):
    """Response for list of exclusion zones."""

    zones: list[ExclusionZoneResponse]
    total: int


class ExclusionZoneImportRequest(BaseModel):
    """Request to import zones from an uploaded file."""

    source_file_id: UUID
    zone_type: str = Field(
        ..., pattern="^(wetland|easement|stream_buffer|setback|custom)$"
    )
    name_prefix: Optional[str] = Field(None, max_length=200)
    buffer_distance: Optional[float] = Field(None, ge=0, le=10000)


class ExclusionZoneImportResponse(BaseModel):
    """Response after importing zones from a file."""

    zones_created: int
    zones: list[ExclusionZoneResponse]
    message: str


class BufferApplyRequest(BaseModel):
    """Request to apply buffer to a zone."""

    buffer_distance: float = Field(
        ..., gt=0, le=10000, description="Buffer distance in meters"
    )


class SpatialQueryRequest(BaseModel):
    """Request for spatial queries against zones."""

    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry to check")

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate GeoJSON geometry structure."""
        if not isinstance(v, dict):
            raise ValueError("Geometry must be a dictionary")
        if "type" not in v:
            raise ValueError("Geometry must have a 'type' field")
        if "coordinates" not in v:
            raise ValueError("Geometry must have a 'coordinates' field")
        return v


class SpatialQueryResponse(BaseModel):
    """Response for spatial queries."""

    intersects: bool
    intersecting_zones: list[ExclusionZoneResponse]
    total_intersecting: int
