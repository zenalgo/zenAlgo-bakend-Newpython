import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_ENV: str = "local"
    APP_PORT: int = 8000
    
    # Database and Caching
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/trading")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # JWT Settings
    JWT_SECRET: str = Field(default="supersecretjwtkeythatisatleast32charslong!")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Dhan Broker API Configuration
    DHAN_API_BASE_URL: str = Field(default="https://api.dhan.co/v2")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
