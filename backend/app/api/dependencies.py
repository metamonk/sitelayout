from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.crud.user import user as user_crud
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import TokenPayload

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode JWT token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # Get user_id from token
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        token_data = TokenPayload(sub=user_id)
    except Exception:
        raise credentials_exception

    # Get user from database
    try:
        user_uuid = UUID(token_data.sub)
    except (ValueError, TypeError, AttributeError):
        raise credentials_exception

    user = user_crud.get(db, user_id=user_uuid)
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to get the current active user.

    Raises:
        HTTPException: If user is inactive
    """
    if not user_crud.is_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to get the current superuser.

    Raises:
        HTTPException: If user is not a superuser
    """
    if not user_crud.is_superuser(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user
