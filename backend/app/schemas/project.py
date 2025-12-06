from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    id: UUID
    user_id: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    # GeoJSON representations of spatial data
    boundary: Optional[dict[str, Any]] = None
    entry_point: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Schema for list of projects response."""

    projects: list[ProjectResponse]
    total: int
    page: int
    page_size: int
