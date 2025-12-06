import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset_placement import AssetPlacement
    from app.models.exclusion_zone import ExclusionZone
    from app.models.road_network import RoadNetwork
    from app.models.terrain_analysis import TerrainAnalysis
    from app.models.uploaded_file import UploadedFile
    from app.models.user import User
    from app.models.volume_estimation import VolumeEstimation


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    EXPORTED = "exported"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT
    )

    # Spatial data - using Any for GeoAlchemy2 types as they lack proper type stubs
    boundary_geom: Mapped[Optional[Any]] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )
    entry_point_geom: Mapped[Optional[Any]] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="project"
    )
    terrain_analyses: Mapped[list["TerrainAnalysis"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    exclusion_zones: Mapped[list["ExclusionZone"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    asset_placements: Mapped[list["AssetPlacement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    road_networks: Mapped[list["RoadNetwork"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    volume_estimations: Mapped[list["VolumeEstimation"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
