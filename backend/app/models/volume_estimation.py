"""Database model for cut/fill volume estimation results."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset_placement import AssetPlacement
    from app.models.project import Project
    from app.models.road_network import RoadNetwork
    from app.models.terrain_analysis import TerrainAnalysis


class VolumeEstimationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class FoundationType(str, enum.Enum):
    PAD = "pad"
    PIER = "pier"
    STRIP = "strip"
    RAFT = "raft"


class VolumeEstimation(Base):
    """Stores cut/fill volume estimation results for a project."""

    __tablename__ = "volume_estimations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )

    # Optional references to source data
    terrain_analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terrain_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_placement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_placements.id", ondelete="SET NULL"),
        nullable=True,
    )
    road_network_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("road_networks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Analysis status and progress tracking
    status: Mapped[VolumeEstimationStatus] = mapped_column(
        SQLEnum(VolumeEstimationStatus), default=VolumeEstimationStatus.PENDING
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Configuration
    grid_resolution: Mapped[float] = mapped_column(
        Float, default=2.0
    )  # Grid cell size in meters (1-10m)
    default_foundation_type: Mapped[FoundationType] = mapped_column(
        SQLEnum(FoundationType), default=FoundationType.PAD
    )
    # Road width in meters
    road_width: Mapped[float] = mapped_column(Float, default=6.0)

    # Asset volume totals
    total_asset_cut_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    total_asset_fill_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    total_asset_net_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    assets_analyzed: Mapped[int] = mapped_column(Integer, default=0)

    # Road volume totals
    total_road_cut_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    total_road_fill_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    total_road_net_volume_m3: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    road_segments_analyzed: Mapped[int] = mapped_column(Integer, default=0)

    # Project totals
    total_cut_volume_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_fill_volume_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_net_volume_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cut_fill_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Detailed breakdown stored as JSON
    # Structure: {"assets": [...], "roads": [...]}
    asset_volumes_detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    road_volumes_detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 3D Visualization data
    # Structure: {"bounds": {...}, "grid": [...], "assets": [...], "roads": [...]}
    visualization_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Volumetric report data
    report_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Analysis bounds
    analysis_bounds: Mapped[Optional[Any]] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )

    # DEM information
    dem_resolution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Processing metadata
    total_cells_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    memory_peak_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Caching support
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cache_valid_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="volume_estimations")
    terrain_analysis: Mapped[Optional["TerrainAnalysis"]] = relationship()
    asset_placement: Mapped[Optional["AssetPlacement"]] = relationship()
    road_network: Mapped[Optional["RoadNetwork"]] = relationship()
