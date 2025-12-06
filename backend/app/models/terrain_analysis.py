import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.uploaded_file import UploadedFile


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"  # Analysis requested, not started
    PROCESSING = "processing"  # Currently running
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Error during processing
    CACHED = "cached"  # Results retrieved from cache


class TerrainAnalysis(Base):
    """Stores terrain analysis results for a project area."""

    __tablename__ = "terrain_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    source_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Analysis status and progress tracking
    status: Mapped[AnalysisStatus] = mapped_column(
        SQLEnum(AnalysisStatus), default=AnalysisStatus.PENDING
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # DEM source information
    dem_source: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # e.g., "SRTM", "USGS", "uploaded"
    dem_resolution: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Resolution in meters
    dem_crs: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # e.g., "EPSG:4326"

    # Analysis bounds - the area analyzed
    analysis_bounds: Mapped[Optional[Any]] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )

    # Elevation statistics
    elevation_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elevation_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elevation_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elevation_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Slope statistics (in degrees)
    slope_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slope_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slope_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slope_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Slope classification breakdown (percentage of area in each class)
    # Stored as JSON: {"flat": 10.5, "gentle": 25.3, ...}
    slope_classification: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Aspect statistics (in degrees, 0-360)
    aspect_distribution: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # e.g., {"N": 12.5, "NE": 15.0, "E": 10.0, ...}

    # Paths to generated raster files (stored on disk)
    slope_raster_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    aspect_raster_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    hillshade_raster_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # File sizes for storage management
    slope_raster_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    aspect_raster_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    hillshade_raster_size: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    # Caching support
    input_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of input params
    cache_valid_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Processing metadata
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    memory_peak_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="terrain_analyses")
    source_file: Mapped[Optional["UploadedFile"]] = relationship()
