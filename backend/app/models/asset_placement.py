"""Asset placement models for BESS auto-placement engine."""

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
    from app.models.project import Project
    from app.models.terrain_analysis import TerrainAnalysis
    from app.models.user import User


class PlacementStatus(str, enum.Enum):
    """Status of asset placement operation."""

    PENDING = "pending"  # Placement requested, not started
    PROCESSING = "processing"  # Currently running
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Error during processing


class OptimizationCriteria(str, enum.Enum):
    """Optimization criteria for asset placement."""

    MINIMIZE_CUT_FILL = "minimize_cut_fill"  # Minimize earthwork (cut/fill operations)
    MAXIMIZE_FLAT_AREAS = "maximize_flat_areas"  # Prefer flatter areas
    MINIMIZE_INTER_ASSET_DISTANCE = (
        "minimize_inter_asset_distance"  # Minimize distances between assets
    )
    BALANCED = "balanced"  # Balanced approach combining multiple criteria


class AssetPlacement(Base):
    """Stores asset auto-placement configurations and results."""

    __tablename__ = "asset_placements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    terrain_analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terrain_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Placement metadata
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status and progress tracking
    status: Mapped[PlacementStatus] = mapped_column(
        SQLEnum(PlacementStatus), default=PlacementStatus.PENDING
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Configuration parameters
    # Asset specifications
    asset_width: Mapped[float] = mapped_column(Float)  # Width of asset in meters
    asset_length: Mapped[float] = mapped_column(Float)  # Length of asset in meters
    asset_count: Mapped[int] = mapped_column(Integer)  # Number of assets to place

    # Grid configuration
    grid_resolution: Mapped[float] = mapped_column(
        Float, default=5.0
    )  # Grid cell size in meters

    # Constraints
    min_spacing: Mapped[float] = mapped_column(
        Float, default=10.0
    )  # Minimum spacing between assets in meters
    max_slope: Mapped[float] = mapped_column(
        Float, default=5.0
    )  # Maximum allowed slope in degrees

    # Area constraints (placement bounds)
    placement_area: Mapped[Optional[Any]] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )

    # Optimization settings
    optimization_criteria: Mapped[OptimizationCriteria] = mapped_column(
        SQLEnum(OptimizationCriteria), default=OptimizationCriteria.BALANCED
    )

    # Advanced settings stored as JSON
    # e.g., {"buffer_from_exclusion_zones": 5.0, "prefer_south_facing": true}
    advanced_settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Results
    # Placed assets stored as MultiPoint geometry
    placed_assets: Mapped[Optional[Any]] = mapped_column(
        Geometry("MULTIPOINT", srid=4326), nullable=True
    )

    # Detailed placement data (each asset with its properties)
    # Format: [{"id": 1, "position": [lon, lat], "elevation": 120.5, ...}, ...]
    placement_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Statistics
    assets_placed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assets_requested: Mapped[int] = mapped_column(Integer)
    placement_success_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Percentage

    # Grid statistics
    grid_cells_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grid_cells_valid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grid_cells_excluded: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Optimization metrics
    avg_slope: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_inter_asset_distance: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    total_cut_fill_volume: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Cubic meters

    # Processing metadata
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    memory_peak_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    algorithm_iterations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="asset_placements")
    user: Mapped["User"] = relationship(back_populates="asset_placements")
    terrain_analysis: Mapped[Optional["TerrainAnalysis"]] = relationship()
