"""
Database setup and session management.
User-isolated paths for multi-user support.
"""

from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# Base directory
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"
DB_PATH = DATA_DIR / "users.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_DIR.mkdir(parents=True, exist_ok=True)

# SQLite Database
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set True for SQL query logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency injection for database sessions.
    Used in FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_dir(user_id: int, create: bool = True) -> Path:
    """
    Get or create user-specific data directory.

    Structure:
    data/users/{user_id}/
    ├── raw/
    ├── normalized/
    ├── processed/
    │   ├── denoised/
    │   └── vad_segments/
    ├── transcriptions/
    └── tmp/

    Args:
        user_id: User ID
        create: Create directories if they don't exist

    Returns:
        Path to user directory
    """
    user_dir = USERS_DIR / str(user_id)

    if create:
        # Create all subdirectories
        subdirs = [
            user_dir / "raw",
            user_dir / "normalized",
            user_dir / "processed" / "denoised",
            user_dir / "processed" / "vad_segments",
            user_dir / "transcriptions",
            user_dir / "outputs",
            user_dir / "tmp"
        ]
        for subdir in subdirs:
            subdir.mkdir(parents=True, exist_ok=True)

    return user_dir


def get_user_config_path(user_id: int) -> dict:
    """
    Get user-specific config paths for pipeline.

    Returns dict matching config.yaml paths structure.
    """
    user_dir = get_user_dir(user_id, create=True)

    return {
        'raw_audio': str(user_dir / 'raw'),
        'normalized_audio': str(user_dir / 'normalized'),
        'denoised_audio': str(user_dir / 'processed' / 'denoised'),
        'vad_segments': str(user_dir / 'processed' / 'vad_segments'),
        'transcriptions': str(user_dir / 'transcriptions'),
        'outputs': str(user_dir / 'outputs'),
        'models': str(BASE_DIR / 'models'),
    }


def cleanup_user_temp(user_id: int) -> None:
    """
    Clean up temporary files for a user.
    """
    user_dir = get_user_dir(user_id)
    temp_dir = user_dir / 'tmp'

    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir)
        # Recreate
        temp_dir.mkdir(parents=True, exist_ok=True)


def cleanup_user_data(user_id: int) -> None:
    """
    Remove all user data when account is deleted.
    """
    user_dir = get_user_dir(user_id)

    if user_dir.exists():
        import shutil
        shutil.rmtree(user_dir)


def get_job_temp_dir(user_id: int, job_id: int) -> Path:
    """
    Get temporary directory for a specific job.
    """
    user_dir = get_user_dir(user_id)
    job_temp = user_dir / 'tmp' / f'job_{job_id}'
    job_temp.mkdir(parents=True, exist_ok=True)
    return job_temp


def init_db():
    """
    Initialize database tables.
    """
    from backend.models.user import User
    from backend.models.config import UserConfig
    from backend.models.pipeline_job import PipelineJob, PipelineStep, UserJobLock, SystemJobLimit

    Base.metadata.create_all(bind=engine)
