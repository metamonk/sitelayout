from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Response after successful file upload."""

    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    message: str


class FileValidationResponse(BaseModel):
    """Response with file validation details."""

    id: UUID
    filename: str
    status: str
    is_valid: bool
    geometry_type: Optional[str] = None
    feature_count: Optional[int] = None
    validation_message: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_description: Optional[str] = None


class UploadedFileResponse(BaseModel):
    """Full uploaded file response."""

    id: UUID
    user_id: UUID
    project_id: Optional[UUID] = None
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    status: str
    validation_message: Optional[str] = None
    geometry_type: Optional[str] = None
    feature_count: Optional[int] = None
    extracted_name: Optional[str] = None
    extracted_description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    # GeoJSON representation of geometry
    boundary: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class UploadedFileListResponse(BaseModel):
    """Response for list of uploaded files."""

    files: list[UploadedFileResponse]
    total: int
    page: int
    page_size: int


class FileAssignRequest(BaseModel):
    """Request to assign a file to a project."""

    project_id: UUID
