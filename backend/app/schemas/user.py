from pydantic import BaseModel, EmailStr
from typing import Optional

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
