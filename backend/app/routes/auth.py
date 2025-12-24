from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer
from datetime import datetime
import httpx

from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.utils.auth_utils import (
    create_jwt,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import mongodb
from app.models.user import USER_COLLECTION, user_dict
from app.schemas.user import (
    UserOut,
    RegisterRequest,
    LoginRequest,
    LogoutResponse,
)
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])
security = HTTPBearer()


# ==================== EMAIL / PASSWORD ====================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """Register user manually with email + password"""
    try:
        existing_user = await mongodb.db[USER_COLLECTION].find_one(
            {"$or": [{"email": data.email}, {"user_name": data.user_name}]}
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or username already registered",
            )

        hashed_pw = hash_password(data.password)

        user = {
            "email": data.email,
            "name": data.name,
            "user_name": data.user_name,
            "hashed_password": hashed_pw,
            "google_id": None,
            "picture": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        await mongodb.db[USER_COLLECTION].insert_one(user)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "User registered successfully"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(data: LoginRequest):
    """Login with email + password"""
    try:
        user = await mongodb.db[USER_COLLECTION].find_one({"email": data.email})
        if not user or not user.get("hashed_password"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_jwt(str(user["_id"]), user["email"], data.rememberMe)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": UserOut(
                id=str(user["_id"]),
                email=user["email"],
                name=user["name"],
                user_name=user["user_name"],
                picture=user.get("picture"),
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """JWT logout (client-side invalidation)"""
    try:
        await mongodb.db[USER_COLLECTION].update_one(
            {"_id": current_user["_id"]},
            {"$set": {"last_logout": datetime.utcnow()}},
        )
        return LogoutResponse(message="Logged out successfully")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    try:
        return UserOut(
            id=str(current_user["_id"]),
            email=current_user["email"],
            name=current_user["name"],
            user_name=current_user["user_name"],
            picture=current_user.get("picture"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== GOOGLE OAUTH – REGISTER ====================

@router.get("/register/google")
def google_register():
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&prompt=consent"
        f"&state=register"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback/register")
async def google_callback_register(code: str | None = None):
    try:
        if not code:
            raise HTTPException(400, "Missing authorization code")

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
            raise HTTPException(400, "Token exchange failed")

        token_data = resp.json()
        id_info = id_token.verify_oauth2_token(
            token_data["id_token"],
            grequests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        existing_user = await mongodb.db[USER_COLLECTION].find_one(
            {"email": id_info["email"]}
        )
        if existing_user:
            raise HTTPException(400, "Account already exists")

        user = {
            "email": id_info["email"],
            "name": id_info.get("name"),
            "user_name": id_info["email"].split("@")[0],
            "google_id": id_info["sub"],
            "picture": id_info.get("picture"),
            "hashed_password": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await mongodb.db[USER_COLLECTION].insert_one(user)
        token = create_jwt(str(result.inserted_id), user["email"])

        return RedirectResponse(
            f"{settings.FRONTEND_URL}/auth/callback?token={token}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== GOOGLE OAUTH – LOGIN ====================

@router.get("/login/google")
def google_login():
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&prompt=consent"
        f"&state=login"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str | None = None):
    try:
        if not code:
            raise HTTPException(400, "Missing authorization code")

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

        token_data = resp.json()
        id_info = id_token.verify_oauth2_token(
            token_data["id_token"],
            grequests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        user = await mongodb.db[USER_COLLECTION].find_one(
            {"email": id_info["email"]}
        )

        if not user:
            user = {
                "email": id_info["email"],
                "name": id_info.get("name"),
                "user_name": id_info["email"].split("@")[0],
                "google_id": id_info["sub"],
                "picture": id_info.get("picture"),
                "hashed_password": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            result = await mongodb.db[USER_COLLECTION].insert_one(user)
            user["_id"] = result.inserted_id

        token = create_jwt(str(user["_id"]), user["email"])

        return RedirectResponse(
            f"{settings.FRONTEND_URL}/auth/callback?token={token}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TOKEN REFRESH ====================

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    try:
        token = create_jwt(str(current_user["_id"]), current_user["email"])
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
