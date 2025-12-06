import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class ZoneType(str, enum.Enum):
    WETLAND = "wetland"
    EASEMENT = "easement"
    STREAM_BUFFER = "stream_buffer"
    SETBACK = "setback"
    CUSTOM = "custom"


class ZoneSource(str, enum.Enum):
    IMPORTED = "imported"  # From file upload
    DRAWN = "drawn"  # Manually drawn on map


class ExclusionZone(Base):
    __tablename__ = "exclusion_zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    # Zone metadata
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zone_type: Mapped[ZoneType] = mapped_column(SQLEnum(ZoneType))
    source: Mapped[ZoneSource] = mapped_column(SQLEnum(ZoneSource))

    # Geometry - stored as PostGIS geometry
    geometry: Mapped[Any] = mapped_column(
        Geometry("GEOMETRY", srid=4326), nullable=False
    )
    geometry_type: Mapped[str] = mapped_column(
        String(50)
    )  # Polygon, MultiPolygon, etc.

    # Buffer configuration
    buffer_distance: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Distance in meters
    buffer_applied: Mapped[bool] = mapped_column(default=False)
    buffered_geometry: Mapped[Optional[Any]] = mapped_column(
        Geometry("GEOMETRY", srid=4326), nullable=True
    )

    # Source file reference (if imported)
    source_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_files.id"), nullable=True
    )

    # Styling (stored for custom zones)
    fill_color: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # Hex color
    stroke_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fill_opacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Area calculation (in square meters)
    area_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        onupdate=func.now(), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="exclusion_zones")
    user: Mapped["User"] = relationship(back_populates="exclusion_zones")
