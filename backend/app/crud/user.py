from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate


class CRUDUser:
    def get(self, db: Session, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get a user by email."""
        return db.query(User).filter(User.email == email).first()

    def get_by_google_id(self, db: Session, google_id: str) -> Optional[User]:
        """Get a user by Google ID."""
        return db.query(User).filter(User.google_id == google_id).first()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> list[User]:
        """Get multiple users with pagination."""
        return db.query(User).offset(skip).limit(limit).all()

    def create(self, db: Session, user_in: UserCreate) -> User:
        """Create a new user with email/password."""
        db_obj = User(
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            oauth_provider="email",
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_oauth_user(
        self,
        db: Session,
        email: str,
        google_id: str,
        full_name: Optional[str] = None,
    ) -> User:
        """Create a new user from OAuth provider."""
        db_obj = User(
            email=email,
            google_id=google_id,
            full_name=full_name,
            oauth_provider="google",
            hashed_password=None,  # OAuth users don't have passwords
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: User, user_in: UserUpdate) -> User:
        """Update a user."""
        update_data = user_in.model_dump(exclude_unset=True)

        # Hash password if provided
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def authenticate(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not user.hashed_password:
            # OAuth user trying to log in with password
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        """Check if user is a superuser."""
        return user.is_superuser


# Create a singleton instance
user = CRUDUser()
