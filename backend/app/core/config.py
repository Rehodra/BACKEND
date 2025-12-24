from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: Optional[str] = "MangaAI"
    DEBUG: Optional[bool] = True
    FRONTEND_URL: Optional[str] = "http://localhost:5173"  # ✅ Added

    # Mongo
    MONGODB_URI: str
    MONGODB_DB: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: Optional[str] = "HS256"
    JWT_EXPIRE_MINUTES: Optional[int] = 60

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str]
    GOOGLE_CLIENT_SECRET: Optional[str]
    GOOGLE_REDIRECT_URI: Optional[str]

    # External APIs
    GEMINI_API_KEY: Optional[str]

    class Config:
        env_file = ".env"


settings = Settings()