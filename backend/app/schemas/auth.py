from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None  # user_id
    exp: Optional[int] = None


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    google_id: Optional[str] = None
    oauth_provider: Optional[str] = None

    class Config:
        from_attributes = True


# OAuth schemas
class GoogleOAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class GoogleUserInfo(BaseModel):
    id: str
    email: str
    verified_email: bool
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
