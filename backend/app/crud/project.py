from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus
from app.schemas.project import ProjectCreate, ProjectUpdate


class CRUDProject:
    def get(self, db: Session, project_id: UUID) -> Optional[Project]:
        """Get a project by ID."""
        return db.query(Project).filter(Project.id == project_id).first()

    def get_by_user(
        self, db: Session, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Project]:
        """Get all projects for a user with pagination."""
        return (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_user(self, db: Session, user_id: UUID) -> int:
        """Get total count of projects for a user."""
        return db.query(Project).filter(Project.user_id == user_id).count()

    def create(self, db: Session, project_in: ProjectCreate, user_id: UUID) -> Project:
        """Create a new project."""
        db_obj = Project(
            name=project_in.name,
            description=project_in.description,
            user_id=user_id,
            status=ProjectStatus.DRAFT,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, db_obj: Project, project_in: ProjectUpdate
    ) -> Project:
        """Update a project."""
        update_data = project_in.model_dump(exclude_unset=True)

        # Handle status conversion
        if "status" in update_data and update_data["status"]:
            try:
                update_data["status"] = ProjectStatus(update_data["status"])
            except ValueError:
                pass  # Keep existing status if invalid

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, project_id: UUID) -> bool:
        """Delete a project."""
        project = self.get(db, project_id)
        if project:
            db.delete(project)
            db.commit()
            return True
        return False

    def to_response_dict(self, project: Project) -> dict[str, Any]:
        """Convert project to response dictionary with GeoJSON."""
        result = {
            "id": project.id,
            "user_id": project.user_id,
            "name": project.name,
            "description": project.description,
            "status": project.status.value,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "boundary": None,
            "entry_point": None,
        }

        # Convert geometry to GeoJSON if present
        if project.boundary_geom is not None:
            try:
                shape = to_shape(project.boundary_geom)
                result["boundary"] = {
                    "type": "Feature",
                    "geometry": shape.__geo_interface__,
                }
            except Exception:
                pass

        if project.entry_point_geom is not None:
            try:
                shape = to_shape(project.entry_point_geom)
                result["entry_point"] = {
                    "type": "Feature",
                    "geometry": shape.__geo_interface__,
                }
            except Exception:
                pass

        return result


# Create a singleton instance
project = CRUDProject()
