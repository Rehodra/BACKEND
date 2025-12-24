from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
import httpx

from app.db import mongodb
from app.schemas.user import UserOut
from app.models.user import USER_COLLECTION, user_dict
from app.core.config import settings

from google.oauth2 import id_token
from google.auth.transport import requests as grequests

router = APIRouter(prefix="/api/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


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


# ==================== HELPERS ====================

def create_jwt(user_id: str, email: str, remember: bool = False) -> str:
    """Create JWT token with configurable expiration"""
    expire = datetime.utcnow() + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES * (24 if remember else 1)
    )
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_jwt(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = verify_jwt(token)
    
    user = await mongodb.db[USER_COLLECTION].find_one({"_id": payload.get("sub")})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


def hash_password(password: str) -> str:
    """Hash password with bcrypt, handling 72-byte limit"""
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes.decode('utf-8', errors='ignore'))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    password_bytes = plain_password.encode('utf-8')[:72]
    password_str = password_bytes.decode('utf-8', errors='ignore')
    return pwd_context.verify(password_str, hashed_password)


# ==================== EMAIL/PASSWORD AUTH ====================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """Register a new user with email and password"""
    
    # Check if email already exists
    existing_email = await mongodb.db[USER_COLLECTION].find_one({"email": data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_username = await mongodb.db[USER_COLLECTION].find_one({"user_name": data.user_name})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user document
    user = {
        "email": data.email,
        "name": data.name,
        "user_name": data.user_name,
        "password": hash_password(data.password),
        "picture": None,
        "google_id": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await mongodb.db[USER_COLLECTION].insert_one(user)
    user["_id"] = result.inserted_id
    
    # Generate token
    token = create_jwt(str(user["_id"]), user["email"])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut(
            user_id=str(user["_id"]),
            email=user["email"],
            name=user["name"],
            picture=None,
        )
    }


@router.post("/login")
async def login(data: LoginRequest):
    """Login with email and password"""
    
    # Find user by email
    user = await mongodb.db[USER_COLLECTION].find_one({"email": data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user has a password (not OAuth-only account)
    if "password" not in user or not user["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google sign-in. Please login with Google."
        )
    
    # Verify password
    if not verify_password(data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    token = create_jwt(str(user["_id"]), user["email"], data.rememberMe)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut(
            user_id=str(user["_id"]),
            email=user["email"],
            name=user.get("name"),
            picture=user.get("picture"),
        )
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout current user
    
    Note: Since we're using stateless JWT tokens, the actual token invalidation
    happens on the client side by removing the token from storage.
    This endpoint primarily serves to:
    1. Verify the token is valid
    2. Log the logout event (optional)
    3. Provide a consistent API pattern
    """
    
    # Optional: Log logout event or update user's last_logout timestamp
    await mongodb.db[USER_COLLECTION].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"last_logout": datetime.utcnow()}}
    )
    
    return LogoutResponse(message="Logged out successfully")


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information"""
    
    return UserOut(
        user_id=str(current_user["_id"]),
        email=current_user["email"],
        name=current_user.get("name"),
        picture=current_user.get("picture"),
    )


# ==================== GOOGLE OAUTH - REGISTER ====================

@router.get("/register/google")
def google_register():
    """
    Initiates Google OAuth for NEW users (registration)
    Redirects to Google with 'register' state parameter
    """
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state=register"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback/register")
async def google_callback_register(code: str | None = None, state: str | None = None):
    """
    Handle Google OAuth callback for REGISTRATION
    Only allows NEW users, rejects existing ones
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code"
        )
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token exchange failed"
        )
    
    token_data = resp.json()
    id_tok = token_data.get("id_token")
    
    # Verify and decode ID token
    id_info = id_token.verify_oauth2_token(
        id_tok,
        grequests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )
    
    google_id = id_info["sub"]
    email = id_info["email"]
    name = id_info.get("name")
    picture = id_info.get("picture")
    
    # Check if user already exists
    existing_user = await mongodb.db[USER_COLLECTION].find_one(
        {"$or": [{"google_id": google_id}, {"email": email}]}
    )
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already exists. Please use login instead."
        )
    
    # Create new user
    user = {
        "email": email,
        "name": name,
        "user_name": email.split("@")[0],  # Default username from email
        "google_id": google_id,
        "picture": picture,
        "password": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await mongodb.db[USER_COLLECTION].insert_one(user)
    user["_id"] = result.inserted_id
    
    # Generate token
    token = create_jwt(str(user["_id"]), user["email"])
    
    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={token}"
    return RedirectResponse(frontend_url)


# ==================== GOOGLE OAUTH - LOGIN ====================

@router.get("/login/google")
def google_login():
    """
    Initiates Google OAuth for EXISTING users (login)
    Auto-registers if user doesn't exist (standard OAuth pattern)
    """
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state=login"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str | None = None, state: str | None = None):
    """
    Handle Google OAuth callback for LOGIN
    Auto-registers new users (industry standard behavior)
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code"
        )
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token exchange failed"
        )
    
    token_data = resp.json()
    id_tok = token_data.get("id_token")
    
    # Verify and decode ID token
    id_info = id_token.verify_oauth2_token(
        id_tok,
        grequests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )
    
    google_id = id_info["sub"]
    email = id_info["email"]
    name = id_info.get("name")
    picture = id_info.get("picture")
    
    # Find or create user
    user = await mongodb.db[USER_COLLECTION].find_one(
        {"$or": [{"google_id": google_id}, {"email": email}]}
    )
    
    if not user:
        # Auto-register new user
        user = {
            "email": email,
            "name": name,
            "user_name": email.split("@")[0],  # Default username from email
            "google_id": google_id,
            "picture": picture,
            "password": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await mongodb.db[USER_COLLECTION].insert_one(user)
        user["_id"] = result.inserted_id
    else:
        # Update existing user's Google info if needed
        await mongodb.db[USER_COLLECTION].update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "google_id": google_id,
                    "picture": picture,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    # Generate token
    token = create_jwt(str(user["_id"]), user["email"])
    
    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={token}"
    return RedirectResponse(frontend_url)


# ==================== TOKEN REFRESH ====================

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    Refresh the access token for the current user
    Useful for extending session without re-login
    """
    new_token = create_jwt(str(current_user["_id"]), current_user["email"])
    
    return {
        "access_token": new_token,
        "token_type": "bearer"
    }