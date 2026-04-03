"""
Pipeline job manager.
Handles concurrency limits, validation, and job lifecycle.
"""

from typing import Optional, Dict, Tuple
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.pipeline_job import PipelineJob, UserJobLock, SystemJobLimit
from backend.models.config import UserConfig
from backend.database import get_user_dir, get_job_temp_dir
from backend.config import settings
from backend.utils.file_utils import (
    validate_file_batch,
    save_uploaded_file,
    cleanup_job_temp
)
from backend.services.config_service import get_user_config_dict_with_paths, reset_user_config


# Max input size: 2GB
MAX_INPUT_SIZE_BYTES = settings.max_input_size_mb * 1024 * 1024

# Max files per job
MAX_FILE_COUNT = settings.max_file_count

# System-wide concurrency limit
MAX_CONCURRENT_JOBS = settings.max_concurrent_jobs

# Per-user concurrency limit
MAX_USER_CONCURRENT = settings.max_user_concurrent


class PipelineJobManager:
    """
    Manages pipeline job lifecycle with concurrency limits.
    """

    def __init__(self, db: Session, ws_manager):
        """
        Initialize job manager.

        Args:
            db: Database session
            ws_manager: WebSocket manager for progress updates
        """
        self.db = db
        self.ws_manager = ws_manager

    def get_active_job_count(self, user_id: int) -> int:
        """
        Get number of active jobs for a user.

        Args:
            user_id: User ID

        Returns:
            Number of running jobs for user
        """
        return self.db.query(PipelineJob).filter_by(
            user_id=user_id,
            status='running'
        ).count()

    def get_system_active_job_count(self) -> int:
        """
        Get number of active jobs system-wide.

        Returns:
            Number of running jobs on system
        """
        return self.db.query(PipelineJob).filter_by(
            status='running'
        ).count()

    def can_start_job(
        self,
        user_id: int,
        source_type: str,
        source_value: str,
        file_paths: Optional[list] = None,
        file_count: int = 0,
        total_size: int = 0
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if job can be started based on concurrency limits.

        Args:
            user_id: User ID
            source_type: Type of source (url, youtube, json, huggingface, local)
            source_value: Source value (URL, path, dataset name, etc.)
            file_paths: List of file paths (for local source type)
            file_count: Number of files
            total_size: Total size in bytes

        Returns:
            (can_start, error_message, job_id)
        """
        # 1. Check per-user limit
        active_user_jobs = self.get_active_job_count(user_id)
        if active_user_jobs >= MAX_USER_CONCURRENT:
            return (
                False,
                f"You already have {active_user_jobs} running job(s). Maximum: {MAX_USER_CONCURRENT}",
                None
            )

        # 2. Check system-wide limit
        active_system_jobs = self.get_system_active_job_count()
        if active_system_jobs >= MAX_CONCURRENT_JOBS:
            return (
                False,
                f"System at capacity ({active_system_jobs}/{MAX_CONCURRENT_JOBS}). Try again later.",
                None
            )

        # 3. Validate file count and size for local source
        if source_type == 'local':
            if file_paths:
                is_valid, errors, size = validate_file_batch(
                    file_paths,
                    MAX_FILE_COUNT,
                    MAX_INPUT_SIZE_BYTES
                )

                if not is_valid:
                    return False, '; '.join(errors), None

                file_count = len(file_paths)
                total_size = size

        # 4. Validate source type
        valid_source_types = ['url', 'youtube', 'json', 'huggingface', 'local']
        if source_type not in valid_source_types:
            return False, f"Invalid source type: {source_type}", None

        # 5. Create job record
        job = PipelineJob(
            user_id=user_id,
            status='pending',
            source_type=source_type,
            source_value=source_value,
            file_count=file_count,
            total_size_bytes=total_size,
            created_at=datetime.utcnow()
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        return True, None, job.id

    def create_user_lock(self, user_id: int, job_id: int) -> None:
        """
        Create user job lock to enforce concurrency limit.
        """
        lock = UserJobLock(
            user_id=user_id,
            job_id=job_id
        )
        self.db.add(lock)
        self.db.commit()

    def create_system_limit(self, job_id: int) -> None:
        """
        Create system job limit record.
        """
        limit = SystemJobLimit(
            job_id=job_id
        )
        self.db.add(limit)
        self.db.commit()

    def release_locks(self, user_id: int, job_id: int) -> None:
        """
        Release all locks for a job.
        """
        self.db.query(UserJobLock).filter_by(user_id=user_id).delete()
        self.db.query(SystemJobLimit).filter_by(job_id=job_id).delete()
        self.db.commit()

    def update_job_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        last_successful_step: Optional[str] = None
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status (pending, running, completed, failed, cancelled)
            error_message: Error description
            error_traceback: Full stack trace
            last_successful_step: Last successful step name
        """
        job = self.db.query(PipelineJob).filter_by(id=job_id).first()
        if not job:
            return

        job.status = status

        if status == 'running':
            job.started_at = datetime.utcnow()
        elif status in ['completed', 'failed', 'cancelled']:
            job.completed_at = datetime.utcnow()

        if error_message:
            job.error_message = error_message

        if error_traceback:
            job.error_traceback = error_traceback

        if last_successful_step:
            job.last_successful_step = last_successful_step

        self.db.commit()

    def get_job(self, job_id: int) -> Optional[PipelineJob]:
        """
        Get job by ID.
        """
        return self.db.query(PipelineJob).filter_by(id=job_id).first()

    def get_user_jobs(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """
        Get jobs for a user.

        Args:
            user_id: User ID
            status: Filter by status (optional)
            limit: Max results
            offset: Offset for pagination

        Returns:
            List of PipelineJob objects
        """
        query = self.db.query(PipelineJob).filter_by(user_id=user_id)

        if status:
            query = query.filter_by(status=status)

        query = query.order_by(PipelineJob.created_at.desc())

        return query.offset(offset).limit(limit).all()

    def delete_job(self, job_id: int, user_id: int) -> bool:
        """
        Delete a job (and release locks).

        Args:
            job_id: Job ID
            user_id: User ID (for ownership check)

        Returns:
            True if deleted, False otherwise
        """
        job = self.get_job(job_id)

        if not job:
            return False

        if job.user_id != user_id:
            return False

        # Can only delete non-running jobs
        if job.status == 'running':
            return False

        # Delete job (cascades will clean up related records)
        self.db.delete(job)
        self.db.commit()

        # Clean up temp files
        cleanup_job_temp(user_id, job_id)

        return True

    def cancel_job(self, job_id: int, user_id: int) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job ID
            user_id: User ID (for ownership check)

        Returns:
            True if cancelled, False otherwise
        """
        job = self.get_job(job_id)

        if not job:
            return False

        if job.user_id != user_id:
            return False

        if job.status != 'running':
            return False

        # Update status
        self.update_job_status(job_id, status='cancelled')

        # Note: subprocess will be killed by pipeline_executor

        return True

    def get_system_status(self) -> Dict:
        """
        Get system status for UI.

        Returns:
            Dictionary with capacity and job counts
        """
        active_system_jobs = self.get_system_active_job_count()

        return {
            'max_concurrent_jobs': MAX_CONCURRENT_JOBS,
            'current_running': active_system_jobs,
            'available_slots': MAX_CONCURRENT_JOBS - active_system_jobs,
        }

    def get_user_status(self, user_id: int) -> Dict:
        """
        Get user status for UI.

        Args:
            user_id: User ID

        Returns:
            Dictionary with job availability info
        """
        active_user_jobs = self.get_active_job_count(user_id)
        active_system_jobs = self.get_system_active_job_count()

        # Get current running job if any
        running_job = self.db.query(PipelineJob).filter_by(
            user_id=user_id,
            status='running'
        ).first()

        can_start = (
            active_user_jobs < MAX_USER_CONCURRENT and
            active_system_jobs < MAX_CONCURRENT_JOBS
        )

        return {
            'can_start_job': can_start,
            'active_job_count': active_user_jobs,
            'active_job_id': running_job.id if running_job else None,
            'max_user_concurrent': MAX_USER_CONCURRENT,
        }

    def create_job_config_file(
        self,
        user_id: int,
        job_id: int
    ) -> Tuple[Path, Dict]:
        """
        Create temporary config file for pipeline execution.

        Args:
            user_id: User ID
            job_id: Job ID

        Returns:
            (config_path, config_dict)
        """
        # Get user config with user-specific paths
        config = get_user_config_dict_with_paths(user_id, self.db)

        # Create temp directory for job
        job_temp = get_job_temp_dir(user_id, job_id)

        # Save config as YAML
        import yaml
        config_path = job_temp / 'config.yaml'
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f)

        return config_path, config