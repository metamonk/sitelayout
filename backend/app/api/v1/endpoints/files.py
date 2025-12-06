import os
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.crud.uploaded_file import uploaded_file as file_crud
from app.db.base import get_db
from app.models.uploaded_file import FileStatus
from app.models.user import User
from app.schemas.file import (
    FileAssignRequest,
    FileUploadResponse,
    FileValidationResponse,
    UploadedFileListResponse,
    UploadedFileResponse,
)
from app.services.file_validation import validate_file

router = APIRouter()

# Ensure upload directory exists
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".kmz", ".kml"}
ALLOWED_MIME_TYPES = {
    "application/vnd.google-earth.kmz",
    "application/vnd.google-earth.kml+xml",
    "application/octet-stream",
    "text/xml",
}


def validate_file_type(file: UploadFile) -> str:
    """Validate uploaded file type and return extension."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    return file_ext[1:]  # Remove the dot


def generate_safe_filename(original_filename: str) -> str:
    """Generate a safe filename from the original."""
    return "".join(c for c in original_filename if c.isalnum() or c in "._-")


def get_unique_filepath(base_path: Path) -> Path:
    """Generate a unique filepath, handling duplicates."""
    if not base_path.exists():
        return base_path

    counter = 1
    original_stem = base_path.stem
    while True:
        new_path = base_path.parent / f"{original_stem}_{counter}{base_path.suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


@router.post(
    "/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    project_id: Optional[UUID] = Query(
        None, description="Optional project to associate with"
    ),
):
    """
    Upload a KMZ or KML file.

    The file will be validated for geometry and stored in the database.
    """
    try:
        # Validate file type
        file_type = validate_file_type(file)

        # Read file content
        contents = await file.read()
        file_size = len(contents)

        # Check file size
        if file_size > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {max_mb:.0f}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

        # Generate safe filename and path
        safe_filename = generate_safe_filename(file.filename or "unnamed")
        file_path = get_unique_filepath(UPLOAD_DIR / safe_filename)

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(contents)

        # Create database record
        db_file = file_crud.create(
            db=db,
            user_id=current_user.id,
            original_filename=file.filename or "unnamed",
            stored_filename=file_path.name,
            file_path=str(file_path.relative_to(UPLOAD_DIR)),
            file_size=file_size,
            file_type=file_type,
            project_id=project_id,
        )

        # Validate file geometry
        validation_result = validate_file(file_path, contents)

        # Update database with validation results
        db_file = file_crud.update_validation_result(db, db_file, validation_result)

        return FileUploadResponse(
            id=db_file.id,
            filename=db_file.stored_filename,
            original_filename=db_file.original_filename,
            file_type=db_file.file_type.value,
            file_size=db_file.file_size,
            status=db_file.status.value,
            message=(
                "File uploaded and validated successfully"
                if db_file.status == FileStatus.VALID
                else f"Validation failed: {db_file.validation_message}"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )


@router.get("/", response_model=UploadedFileListResponse)
def list_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
):
    """
    List all uploaded files for the current user.
    """
    skip = (page - 1) * page_size

    if project_id:
        files = file_crud.get_by_project(
            db, project_id=project_id, skip=skip, limit=page_size
        )
        # Verify user owns the project's files
        files = [f for f in files if f.user_id == current_user.id]
        total = len(files)
    else:
        files = file_crud.get_by_user(
            db, user_id=current_user.id, skip=skip, limit=page_size
        )
        total = file_crud.get_count_by_user(db, user_id=current_user.id)

    return {
        "files": [file_crud.to_response_dict(f) for f in files],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{file_id}", response_model=UploadedFileResponse)
def get_file(
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get details of a specific uploaded file.
    """
    file_obj = file_crud.get(db, file_id=file_id)

    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if file_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    return file_crud.to_response_dict(file_obj)


@router.get("/{file_id}/validation", response_model=FileValidationResponse)
def get_file_validation(
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get validation details for an uploaded file.
    """
    file_obj = file_crud.get(db, file_id=file_id)

    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if file_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    return FileValidationResponse(
        id=file_obj.id,
        filename=file_obj.stored_filename,
        status=file_obj.status.value,
        is_valid=file_obj.status == FileStatus.VALID,
        geometry_type=file_obj.geometry_type,
        feature_count=file_obj.feature_count,
        validation_message=file_obj.validation_message,
        extracted_name=file_obj.extracted_name,
        extracted_description=file_obj.extracted_description,
    )


@router.post("/{file_id}/revalidate", response_model=FileValidationResponse)
async def revalidate_file(
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Re-validate an uploaded file.
    """
    file_obj = file_crud.get(db, file_id=file_id)

    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if file_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    # Read file from disk
    file_path = UPLOAD_DIR / file_obj.file_path
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File no longer exists on disk",
        )

    with open(file_path, "rb") as f:
        contents = f.read()

    # Re-validate
    validation_result = validate_file(file_path, contents)
    file_obj = file_crud.update_validation_result(db, file_obj, validation_result)

    return FileValidationResponse(
        id=file_obj.id,
        filename=file_obj.stored_filename,
        status=file_obj.status.value,
        is_valid=file_obj.status == FileStatus.VALID,
        geometry_type=file_obj.geometry_type,
        feature_count=file_obj.feature_count,
        validation_message=file_obj.validation_message,
        extracted_name=file_obj.extracted_name,
        extracted_description=file_obj.extracted_description,
    )


@router.patch("/{file_id}/assign", response_model=UploadedFileResponse)
def assign_file_to_project(
    file_id: UUID,
    request: FileAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Assign an uploaded file to a project.
    """
    file_obj = file_crud.get(db, file_id=file_id)

    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if file_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this file",
        )

    # Verify project exists and belongs to user
    from app.crud.project import project as project_crud

    project = project_crud.get(db, project_id=request.project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    file_obj = file_crud.assign_to_project(db, file_obj, request.project_id)
    return file_crud.to_response_dict(file_obj)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete an uploaded file.
    """
    file_obj = file_crud.get(db, file_id=file_id)

    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if file_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this file",
        )

    # Delete file from disk
    file_path = UPLOAD_DIR / file_obj.file_path
    if file_path.exists():
        try:
            os.remove(file_path)
        except Exception:
            pass  # Continue even if file deletion fails

    # Delete from database
    file_crud.delete(db, file_id=file_id)
    return None
