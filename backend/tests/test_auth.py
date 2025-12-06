import os

# Set environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ALGORITHM"] = "HS256"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://localhost:8000"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import get_db  # noqa: E402
from app.main import fastapi_app as app  # noqa: E402
from app.models.user import User  # noqa: E402

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create tables before each test and drop after."""
    # Only create User table, not Project (to avoid PostGIS dependency)
    User.__table__.create(bind=engine, checkfirst=True)
    yield
    User.__table__.drop(bind=engine, checkfirst=True)


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    }


class TestUserRegistration:
    """Test user registration endpoint."""

    def test_register_new_user(self, setup_database, test_user_data):
        """Test successful user registration."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["full_name"] == test_user_data["full_name"]
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, setup_database, test_user_data):
        """Test registration with existing email."""
        # Register first user
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )

        # Try to register with same email
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, setup_database):
        """Test registration with invalid email."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "invalid-email",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, setup_database):
        """Test registration with short password."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoints."""

    def test_login_success(self, setup_database, test_user_data):
        """Test successful login."""
        # Register user first
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )

        # Login with form data (OAuth2 format)
        response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_json_success(self, setup_database, test_user_data):
        """Test successful login with JSON body."""
        # Register user first
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )

        # Login with JSON
        response = client.post(
            f"{settings.API_V1_STR}/auth/login/json",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, setup_database, test_user_data):
        """Test login with wrong password."""
        # Register user first
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )

        # Try to login with wrong password
        response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": test_user_data["email"],
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, setup_database):
        """Test login with non-existent user."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "somepassword",
            },
        )
        assert response.status_code == 401


class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication."""

    def test_get_current_user(self, setup_database, test_user_data):
        """Test getting current user info."""
        # Register and login
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        token = login_response.json()["access_token"]

        # Get current user
        response = client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["full_name"] == test_user_data["full_name"]

    def test_get_current_user_no_token(self, setup_database):
        """Test accessing protected endpoint without token."""
        response = client.get(f"{settings.API_V1_STR}/auth/me")
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, setup_database):
        """Test accessing protected endpoint with invalid token."""
        response = client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_refresh_token(self, setup_database, test_user_data):
        """Test token refresh."""
        # Register and login
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        token = login_response.json()["access_token"]

        # Refresh token
        response = client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Note: tokens may be identical if refreshed within the same second
        # since JWT payload includes expiration timestamp


class TestLogout:
    """Test logout endpoint."""

    def test_logout(self, setup_database):
        """Test logout endpoint."""
        response = client.post(f"{settings.API_V1_STR}/auth/logout")
        assert response.status_code == 200
        assert "message" in response.json()


class TestGoogleOAuth:
    """Test Google OAuth endpoints."""

    def test_google_authorize_url(self, setup_database):
        """Test getting Google OAuth authorization URL."""
        # This will fail if Google OAuth is not configured
        # but should return proper error
        response = client.get(f"{settings.API_V1_STR}/auth/google/authorize")
        # Either success (200) or not configured (501)
        assert response.status_code in [200, 501]

    def test_google_oauth_not_configured(self, setup_database):
        """Test Google OAuth when not configured."""
        # Save original values
        original_client_id = settings.GOOGLE_CLIENT_ID

        # Temporarily set to empty
        settings.GOOGLE_CLIENT_ID = ""

        response = client.post(
            f"{settings.API_V1_STR}/auth/google",
            json={
                "code": "fake_code",
                "redirect_uri": "http://localhost:3000/callback",
            },
        )
        assert response.status_code == 501
        assert "not configured" in response.json()["detail"].lower()

        # Restore original value
        settings.GOOGLE_CLIENT_ID = original_client_id


class TestPasswordSecurity:
    """Test password hashing and verification."""

    def test_password_not_stored_plain(self, setup_database, test_user_data):
        """Test that passwords are hashed and not stored in plain text."""
        # Register user
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=test_user_data,
        )

        # Get user from database
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == test_user_data["email"]).first()

        # Password should be hashed, not plain text
        assert user.hashed_password != test_user_data["password"]
        assert user.hashed_password.startswith("$2b$")  # bcrypt hash
        db.close()
