"""
Pipeline job models.
Tracks pipeline execution, status, and concurrency limits.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger, func
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class PipelineJob(Base):
    """
    Pipeline execution job.
    """
    __tablename__ = "pipeline_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # pending, running, completed, failed, cancelled

    # Source information
    source_type = Column(String(20), nullable=False)  # url, youtube, json, huggingface, local
    source_value = Column(Text, nullable=False)

    # Execution details
    config_snapshot = Column(Text, nullable=True)  # JSON config at job start (without tokens)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    last_successful_step = Column(String(30), nullable=True)

    # Statistics
    file_count = Column(Integer, nullable=True)
    total_size_bytes = Column(BigInteger, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PipelineJob(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class PipelineStep(Base):
    """
    Individual step progress within a pipeline job.
    """
    __tablename__ = "pipeline_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("pipeline_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(30), nullable=False)  # download, normalize, denoise, segment, transcribe, filter, push
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    progress = Column(Integer, nullable=True)  # 0-100
    message = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, server_default=func.now(), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PipelineStep(id={self.id}, job_id={self.job_id}, step='{self.step_name}')>"


class UserJobLock(Base):
    """
    Ensures user can only have 1 running job at a time.
    """
    __tablename__ = "user_job_locks"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    job_id = Column(Integer, ForeignKey("pipeline_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    locked_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UserJobLock(user_id={self.user_id}, job_id={self.job_id})>"


class SystemJobLimit(Base):
    """
    Tracks system-wide concurrent job limit (max 3).
    """
    __tablename__ = "system_job_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("pipeline_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<SystemJobLimit(id={self.id}, job_id={self.job_id})>"