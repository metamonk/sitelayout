import enum
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    EXPORTED = "exported"


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status: Column[ProjectStatus] = Column(
        SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT
    )

    # Spatial data
    boundary_geom = Column(Geometry("POLYGON", srid=4326), nullable=True)
    entry_point_geom = Column(Geometry("POINT", srid=4326), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="projects")
