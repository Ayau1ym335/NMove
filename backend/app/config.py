from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "NMove"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:Ayaulym^2011@localhost:5433/stridex"
    GEMINI_API_KEY: "AIzaSyDKcfO8GYnPbm_iePXSzM0BFtwF3Vt0Y0A"
    GEMINI_MODEL: str = "gemini-3-pro"
    
    SECRET_KEY: str = "51839332ecca178ca04e0867313ef88da42072eb56414c1934c851d4757983d7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 21600

    
    BOOKS_FOLDER: str = "books"
    DB_REF_FOLDER: str = "db_ref"
    
    MAX_CHAT_HISTORY: int = 50
    CONTEXT_WINDOW_SIZE: int = 3
    
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()

