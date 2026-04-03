"""
Web backend configuration.
Server settings, JWT secrets, encryption keys.
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent


def parse_cors_origins(v: str) -> List[str]:
    """Parse comma-separated CORS origins string."""
    if not v:
        return []
    origins = [s.strip() for s in v.split(',') if s.strip()]
    return [o for o in origins if o]


class Settings(BaseSettings):
    """
    Application settings from environment variables and defaults.
    """
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=False, description="Enable auto-reload")

    # Auth
    secret_key: str = Field(
        ...,
        description="JWT secret key. Required! Use SECRET_KEY env var."
    )
    access_token_expire_minutes: int = Field(default=60, description="JWT access token expiration in minutes")

    # Database
    database_url: Optional[str] = Field(default=None, description="Database URL (defaults to SQLite)")

    # Pipeline limits
    max_concurrent_jobs: int = Field(default=3, description="Max concurrent jobs system-wide")
    max_user_concurrent: int = Field(default=1, description="Max concurrent jobs per user")
    max_input_size_mb: int = Field(default=2048, description="Max input size in MB")
    max_file_count: int = Field(default=5, description="Max files per job")

    # Config encryption
    config_encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for sensitive config values (HF tokens)"
    )

    # CORS origins (comma-separated string for .env, parsed to list at runtime)
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Allowed CORS origins (comma-separated)",
        validate_default=True
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        return parse_cors_origins(self.cors_origins)

    class Config(SettingsConfigDict):
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

# Global settings instance
settings = Settings()


def get_config_encryption_key() -> Optional[str]:
    """
    Get encryption key for config values.
    Falls back to JWT secret if not set.
    """
    return settings.config_encryption_key or settings.secret_key


def validate_encryption_key() -> bool:
    """
    Validate that encryption key is properly configured.
    """
    key = get_config_encryption_key()
    return key and len(key) >= 32
