from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy.orm import Session

from app.models.uploaded_file import FileStatus, FileType, UploadedFile
from app.services.file_validation import ValidationResult


class CRUDUploadedFile:
    def get(self, db: Session, file_id: UUID) -> Optional[UploadedFile]:
        """Get an uploaded file by ID."""
        return db.query(UploadedFile).filter(UploadedFile.id == file_id).first()

    def get_by_user(
        self, db: Session, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[UploadedFile]:
        """Get all files for a user with pagination."""
        return (
            db.query(UploadedFile)
            .filter(UploadedFile.user_id == user_id)
            .order_by(UploadedFile.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_project(
        self, db: Session, project_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[UploadedFile]:
        """Get all files for a project with pagination."""
        return (
            db.query(UploadedFile)
            .filter(UploadedFile.project_id == project_id)
            .order_by(UploadedFile.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_user(self, db: Session, user_id: UUID) -> int:
        """Get total count of files for a user."""
        return db.query(UploadedFile).filter(UploadedFile.user_id == user_id).count()

    def get_by_hash(
        self, db: Session, user_id: UUID, content_hash: str
    ) -> Optional[UploadedFile]:
        """Get a file by content hash for duplicate detection."""
        return (
            db.query(UploadedFile)
            .filter(
                UploadedFile.user_id == user_id,
                UploadedFile.content_hash == content_hash,
            )
            .first()
        )

    def create(
        self,
        db: Session,
        user_id: UUID,
        original_filename: str,
        stored_filename: str,
        file_path: str,
        file_size: int,
        file_type: str,
        project_id: Optional[UUID] = None,
    ) -> UploadedFile:
        """Create a new uploaded file record."""
        db_obj = UploadedFile(
            user_id=user_id,
            project_id=project_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=FileType(file_type.lower()),
            status=FileStatus.PENDING,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_validation_result(
        self, db: Session, db_obj: UploadedFile, validation: ValidationResult
    ) -> UploadedFile:
        """Update file with validation results."""
        db_obj.content_hash = validation.content_hash

        if validation.is_valid and validation.geometry_result:
            db_obj.status = FileStatus.VALID
            db_obj.validation_message = None
            db_obj.geometry_type = validation.geometry_result.geometry_type
            db_obj.feature_count = validation.geometry_result.feature_count
            db_obj.extracted_name = validation.geometry_result.name
            db_obj.extracted_description = validation.geometry_result.description

            # Store geometry in PostGIS
            if validation.geometry_result.geometry:
                db_obj.boundary_geom = from_shape(
                    validation.geometry_result.geometry, srid=4326
                )
        else:
            db_obj.status = FileStatus.INVALID
            db_obj.validation_message = validation.error_message

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        db_obj: UploadedFile,
        status: FileStatus,
        message: Optional[str] = None,
    ) -> UploadedFile:
        """Update file status."""
        db_obj.status = status
        if message:
            db_obj.validation_message = message
        if status == FileStatus.PROCESSED:
            db_obj.processed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def assign_to_project(
        self, db: Session, db_obj: UploadedFile, project_id: UUID
    ) -> UploadedFile:
        """Assign a file to a project."""
        db_obj.project_id = project_id
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, file_id: UUID) -> bool:
        """Delete an uploaded file record."""
        file_obj = self.get(db, file_id)
        if file_obj:
            db.delete(file_obj)
            db.commit()
            return True
        return False

    def to_response_dict(self, file_obj: UploadedFile) -> dict[str, Any]:
        """Convert uploaded file to response dictionary with GeoJSON."""
        result = {
            "id": file_obj.id,
            "user_id": file_obj.user_id,
            "project_id": file_obj.project_id,
            "original_filename": file_obj.original_filename,
            "stored_filename": file_obj.stored_filename,
            "file_type": file_obj.file_type.value,
            "file_size": file_obj.file_size,
            "status": file_obj.status.value,
            "validation_message": file_obj.validation_message,
            "geometry_type": file_obj.geometry_type,
            "feature_count": file_obj.feature_count,
            "extracted_name": file_obj.extracted_name,
            "extracted_description": file_obj.extracted_description,
            "created_at": file_obj.created_at,
            "updated_at": file_obj.updated_at,
            "processed_at": file_obj.processed_at,
            "boundary": None,
        }

        # Convert geometry to GeoJSON if present
        if file_obj.boundary_geom is not None:
            try:
                shape_obj = to_shape(file_obj.boundary_geom)
                result["boundary"] = {  # type: ignore[assignment]
                    "type": "Feature",
                    "geometry": shape_obj.__geo_interface__,
                }
            except Exception:
                pass

        return result


# Create a singleton instance
uploaded_file = CRUDUploadedFile()
