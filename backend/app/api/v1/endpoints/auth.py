from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user import user as user_crud
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import (
    GoogleOAuthRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Register a new user with email and password.
    """
    # Check if user already exists
    user = user_crud.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = user_crud.create(db, user_in=user_in)
    return user


@router.post("/login", response_model=Token)
def login(
    db: Annotated[Session, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """
    Login with email and password to get access token.

    OAuth2 compatible token login, get an access token for future requests.
    """
    # Authenticate user
    user = user_crud.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user_crud.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/json", response_model=Token)
def login_json(
    user_in: UserLogin,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Login with JSON body (alternative to form-based login).
    """
    # Authenticate user
    user = user_crud.authenticate(db, email=user_in.email, password=user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user_crud.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
def refresh_token(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Refresh access token for the current user.
    """
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get current authenticated user.
    """
    return current_user


@router.post("/logout")
def logout():
    """
    Logout endpoint (client-side token deletion).

    Note: JWT tokens are stateless, so logout is handled client-side
    by deleting the token. This endpoint is provided for API completeness.
    """
    return {"message": "Successfully logged out"}


# Google OAuth endpoints
@router.post("/google", response_model=Token)
def google_oauth(
    oauth_request: GoogleOAuthRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Authenticate with Google OAuth.

    Verify the ID token from Google and create or login user.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            oauth_request.code,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        # Get user info
        google_id = idinfo["sub"]
        email = idinfo["email"]
        name = idinfo.get("name")

        # Check if user exists by Google ID
        user = user_crud.get_by_google_id(db, google_id=google_id)

        if not user:
            # Check if user exists by email (linking accounts)
            user = user_crud.get_by_email(db, email=email)
            if user:
                # Link Google account to existing user
                if not user.google_id:
                    user.google_id = google_id
                    user.oauth_provider = "google"
                    db.add(user)
                    db.commit()
                    db.refresh(user)
            else:
                # Create new user
                user = user_crud.create_oauth_user(
                    db, email=email, google_id=google_id, full_name=name
                )

        # Check if user is active
        if not user_crud.is_active(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError as e:
        # Invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google OAuth error: {str(e)}",
        )


@router.get("/google/authorize")
def google_authorize():
    """
    Get Google OAuth authorization URL.

    Returns the URL the client should redirect to for Google OAuth.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    # Build authorization URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        "access_type=offline&"
        "redirect_uri=http://localhost:3000/auth/google/callback"
    )

    return {"authorization_url": auth_url}
