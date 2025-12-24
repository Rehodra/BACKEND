from pydantic import BaseModel, EmailStr
from typing import Optional
from pydantic import field_validator

class UserCreate(BaseModel): # for user creation signup via Google OAuth
    email: EmailStr
    name: str
    google_id: str
    picture: Optional[str]


class UserCreateManual(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserInDB(BaseModel):
    id: Optional[str]
    email: EmailStr
    name: str
    user_name: str
    hashed_password: str
    picture: Optional[str]


class UserOut(BaseModel): # for returning via API
    id: str
    email: EmailStr
    name: str
    user_name: str
    picture: Optional[str]

# ==================== SCHEMAS ====================

class RegisterRequest(BaseModel):
    email: EmailStr
    user_name: str
    password: str
    name: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password is too long (max 72 characters)')
        return v
    
    @field_validator('user_name')
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 30:
            raise ValueError('Username must be less than 30 characters')
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    rememberMe: bool = False


class LogoutResponse(BaseModel):
    message: str