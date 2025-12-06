"""Road network models for automatic road generation."""

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
    from app.models.terrain_analysis import TerrainAnalysis
    from app.models.user import User


class RoadNetworkStatus(str, enum.Enum):
    """Status of road network generation operation."""

    PENDING = "pending"  # Generation requested, not started
    PROCESSING = "processing"  # Currently running
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Error during processing


class RoadOptimizationCriteria(str, enum.Enum):
    """Optimization criteria for road network generation."""

    MINIMAL_LENGTH = "minimal_length"  # Minimize total road length
    MINIMAL_EARTHWORK = "minimal_earthwork"  # Minimize cut/fill volumes
    BALANCED = "balanced"  # Balance between length and earthwork
    MINIMAL_GRADE = "minimal_grade"  # Prefer flatter roads (longer routes)


class RoadNetwork(Base):
    """Stores road network generation configurations and results."""

    __tablename__ = "road_networks"

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
    asset_placement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_placements.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Road network metadata
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status and progress tracking
    status: Mapped[RoadNetworkStatus] = mapped_column(
        SQLEnum(RoadNetworkStatus), default=RoadNetworkStatus.PENDING
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Configuration parameters
    # Road specifications
    road_width: Mapped[float] = mapped_column(
        Float, default=6.0
    )  # Width in meters (6-8m typical)
    max_grade: Mapped[float] = mapped_column(
        Float, default=12.0
    )  # Maximum grade percentage (12% for construction vehicles)
    min_curve_radius: Mapped[float] = mapped_column(
        Float, default=15.0
    )  # Minimum turning radius in meters

    # Grid/pathfinding resolution
    grid_resolution: Mapped[float] = mapped_column(
        Float, default=5.0
    )  # Grid cell size in meters

    # Optimization settings
    optimization_criteria: Mapped[RoadOptimizationCriteria] = mapped_column(
        SQLEnum(RoadOptimizationCriteria), default=RoadOptimizationCriteria.BALANCED
    )

    # Buffer distances from exclusion zones
    exclusion_buffer: Mapped[float] = mapped_column(
        Float, default=5.0
    )  # Buffer from exclusion zones in meters

    # Entry point (site access point)
    entry_point: Mapped[Optional[Any]] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True
    )

    # Advanced settings stored as JSON (prefer_contours, allow_cut_through, etc.)
    advanced_settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Results
    # Road centerlines stored as MultiLineString geometry
    road_centerlines: Mapped[Optional[Any]] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326), nullable=True
    )

    # Road polygons (with width applied) for visualization
    road_polygons: Mapped[Optional[Any]] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=True
    )

    # Detailed road segment data
    # Format: {"segments": [...], "intersections": [...]}
    road_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Statistics
    total_road_length: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Total length in meters
    total_segments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_intersections: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Grade statistics
    avg_grade: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Average grade percentage
    max_grade_actual: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Actual max grade
    grade_compliant: Mapped[Optional[bool]] = mapped_column(
        nullable=True
    )  # All grades within constraint

    # Earthwork estimates
    total_cut_volume: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Cubic meters
    total_fill_volume: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Cubic meters
    net_earthwork_volume: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Cut - Fill

    # Connectivity metrics
    assets_connected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    connectivity_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Percentage

    # Processing metadata
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    memory_peak_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    algorithm_iterations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pathfinding_algorithm: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # e.g., "astar", "dijkstra"

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="road_networks")
    user: Mapped["User"] = relationship(back_populates="road_networks")
    terrain_analysis: Mapped[Optional["TerrainAnalysis"]] = relationship()
    asset_placement: Mapped[Optional["AssetPlacement"]] = relationship()
