import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class FileStatus(str, enum.Enum):
    PENDING = "pending"  # File uploaded, not yet validated
    VALIDATING = "validating"  # Currently being validated
    VALID = "valid"  # Passed validation
    INVALID = "invalid"  # Failed validation
    PROCESSING = "processing"  # Being processed for analysis
    PROCESSED = "processed"  # Processing complete
    ERROR = "error"  # Error during processing


class FileType(str, enum.Enum):
    KMZ = "kmz"
    KML = "kml"


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[FileType] = mapped_column(SQLEnum(FileType))
    file_size: Mapped[int] = mapped_column(BigInteger)  # Size in bytes
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 hash

    # Processing status
    status: Mapped[FileStatus] = mapped_column(
        SQLEnum(FileStatus), default=FileStatus.PENDING
    )
    validation_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extracted geometry - using Any for GeoAlchemy2 types
    boundary_geom: Mapped[Optional[Any]] = mapped_column(
        Geometry("GEOMETRY", srid=4326), nullable=True
    )
    geometry_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Point, LineString, Polygon, etc.
    feature_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Extracted metadata from file
    extracted_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extracted_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="uploaded_files")
    project: Mapped[Optional["Project"]] = relationship(back_populates="uploaded_files")
