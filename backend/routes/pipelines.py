"""
Pipeline routes.
Job CRUD, cancel, retry, status, logs.
"""

from typing import List, Optional
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import tempfile
import zipfile
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from backend.database import get_db
from backend.models.pipeline_job import PipelineJob, PipelineStep
from backend.routes.auth import require_auth
from backend.models.user import User
from backend.services.pipeline_manager import PipelineJobManager
from backend.services.pipeline_executor import BackgroundJobScheduler
from backend.database import SessionLocal
from backend.services.config_service import get_user_config_dict_with_paths
from backend.utils.file_utils import validate_file_batch, ALLOWED_AUDIO_EXTENSIONS
from backend.config import settings


router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


# Pydantic models
class PipelineCreateRequest(BaseModel):
    """Create pipeline job request."""
    source_type: str  # url, youtube, json, huggingface, local
    source_value: str  # URL, path, dataset name, etc.
    skip_download: Optional[bool] = False
    skip_push: Optional[bool] = False


class PipelineResponse(BaseModel):
    """Pipeline job response."""
    id: int
    user_id: int
    status: str
    source_type: str
    source_value: str
    error_message: Optional[str] = None
    last_successful_step: Optional[str] = None
    file_count: Optional[int] = None
    total_size_bytes: Optional[int] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_step: Optional[str] = None
    overall_progress: int = 0


class PipelineListResponse(BaseModel):
    items: List[PipelineResponse]
    page: int
    limit: int
    total: int
    pages: int


class SystemStatusResponse(BaseModel):
    """System status response."""
    max_concurrent_jobs: int
    current_running: int
    available_slots: int


class UserStatusResponse(BaseModel):
    """User status response."""
    can_start_job: bool
    active_job_count: int
    active_job_id: Optional[int] = None
    max_user_concurrent: int


# Dependencies
def get_pipeline_manager(request: Request, db: Session = Depends(get_db)):
    """Get pipeline manager instance (uses app.state.ws_manager)."""
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is None:
        raise RuntimeError("WebSocket manager is not initialized on app.state")
    return PipelineJobManager(db, ws_manager)


def get_scheduler(request: Request, db: Session = Depends(get_db)):
    """Get job scheduler instance (uses app.state.ws_manager/app.state.executor)."""
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is None:
        raise RuntimeError("WebSocket manager is not initialized on app.state")

    executor = getattr(request.app.state, "executor", None)
    return BackgroundJobScheduler(
        ws_manager=ws_manager,
        executor=executor,
        db_factory=SessionLocal,
    )


def _get_job_progress(db: Session, job_id: int) -> tuple[Optional[str], int]:
    steps = db.query(PipelineStep).filter_by(job_id=job_id).all()
    if not steps:
        return None, 0

    # Current step: prefer running, otherwise last completed, otherwise None.
    running = next((s for s in steps if s.status == 'running'), None)
    if running:
        current_step = running.step_name
    else:
        completed_names = {s.step_name for s in steps if s.status == 'completed'}
        current_step = None
        for name in ['download', 'normalize', 'noise_reduction', 'vad_segmentation', 'transcription', 'filter', 'push']:
            if name in completed_names:
                current_step = name
            else:
                break

    total = 0
    for s in steps:
        if s.status == 'completed':
            total += 100
        elif s.status == 'failed':
            total += int(s.progress or 0)
        else:
            total += int(s.progress or 0)

    overall = int(round(total / (len(steps) * 100) * 100))
    overall = max(0, min(100, overall))
    return current_step, overall


def _job_to_response(db: Session, job: PipelineJob) -> PipelineResponse:
    current_step, overall_progress = _get_job_progress(db, job.id)
    return PipelineResponse(
        id=job.id,
        user_id=job.user_id,
        status=job.status,
        source_type=job.source_type,
        source_value=job.source_value,
        error_message=job.error_message,
        last_successful_step=job.last_successful_step,
        file_count=job.file_count,
        total_size_bytes=job.total_size_bytes,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        current_step=current_step,
        overall_progress=overall_progress,
    )


def _naive_utc_to_ts(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Get system status.
    Shows capacity and current running jobs.
    """
    status = manager.get_system_status()
    return SystemStatusResponse(**status)


@router.get("/system/user-status", response_model=UserStatusResponse)
def get_user_status(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Get user-specific status.
    Shows if user can start new job.
    """
    status = manager.get_user_status(current_user.id)
    return UserStatusResponse(**status)


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_job(
    request_data: PipelineCreateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager),
    scheduler: BackgroundJobScheduler = Depends(get_scheduler)
):
    """
    Create and execute a new pipeline job.

    Validates:
    - Concurrency limits (1 per user, 3 system-wide)
    - File count (max 5)
    - Total size (max 2GB)
    """
    # Validate source type
    valid_types = ['url', 'youtube', 'json', 'huggingface', 'local']
    if request_data.source_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type. Must be one of: {', '.join(valid_types)}"
        )

    # For local source, we need file info from upload
    file_paths = []
    file_count = 0
    total_size = 0

    if request_data.source_type == 'local':
        # Files should be uploaded separately
        # For now, assume source_value is directory path
        from pathlib import Path
        source_path = Path(request_data.source_value)

        if source_path.exists() and source_path.is_dir():
            import os
            for item in os.listdir(source_path):
                file_path = source_path / item
                if file_path.is_file() and file_path.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
                    file_paths.append(file_path)

            file_count = len(file_paths)
            total_size = sum(fp.stat().st_size for fp in file_paths)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Local source path does not exist or is not a directory"
            )

    # Create and execute job in background (scheduler performs concurrency checks)
    result = await scheduler.schedule_and_execute(
        user_id=current_user.id,
        source_type=request_data.source_type,
        source_value=request_data.source_value,
        file_paths=file_paths,
        file_count=file_count,
        total_size=total_size,
        skip_download=request_data.skip_download,
        skip_push=request_data.skip_push
    )

    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get('error') or 'Cannot start job'
        )

    job_id = int(result['job_id'])

    # Get created job
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job was created but could not be loaded"
        )

    return _job_to_response(db, job)


@router.get("", response_model=PipelineListResponse)
def list_pipeline_jobs(
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    # Back-compat with older clients
    status_filter: Optional[str] = None,
    offset: Optional[int] = None,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    List user's pipeline jobs.

    Supports filtering by status and pagination.
    """
    page = max(1, int(page))
    limit = max(1, min(100, int(limit)))

    eff_status = status_filter or status

    query = db.query(PipelineJob).filter_by(user_id=current_user.id)
    if eff_status:
        query = query.filter_by(status=eff_status)

    total = query.count()

    if offset is None:
        offset = (page - 1) * limit
    else:
        offset = max(0, int(offset))

    jobs = (
        query.order_by(PipelineJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    pages = max(1, int(math.ceil(total / limit))) if total > 0 else 1

    return PipelineListResponse(
        items=[_job_to_response(db, job) for job in jobs],
        page=page,
        limit=limit,
        total=total,
        pages=pages,
    )


@router.get("/{job_id}", response_model=PipelineResponse)
def get_pipeline_job(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Get details of a specific pipeline job.
    """
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Check ownership
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return _job_to_response(db, job)


@router.get("/{job_id}/download")
def download_processed_outputs(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager),
):
    """
    Download processed outputs as a ZIP archive for a given job.

    Note: Pipeline outputs are stored under user directories (not per-job). We filter by file mtime using the job's
    started/completed timestamps to approximate which files belong to this run.
    """
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    start_dt = job.started_at or job.created_at
    end_dt = job.completed_at or datetime.utcnow()

    # Include some slack because file mtimes may be slightly outside timestamps (copy/move operations, etc.)
    if start_dt:
        start_dt = start_dt - timedelta(minutes=2)
    if end_dt:
        end_dt = end_dt + timedelta(minutes=2)

    start_ts = _naive_utc_to_ts(start_dt)
    end_ts = _naive_utc_to_ts(end_dt)

    cfg = get_user_config_dict_with_paths(current_user.id, db, mask_sensitive=False) or {}
    paths = cfg.get("paths") if isinstance(cfg.get("paths"), dict) else {}

    outputs_dir = Path(paths.get("outputs")) if paths.get("outputs") else None
    job_outputs_dir = (outputs_dir / "jobs" / f"job_{job_id}") if outputs_dir else None

    # Build a strict, user-facing ZIP layout:
    #   <video_name>/*.wav
    #   <video_name>/transcription.json
    #
    # Prefer the new exported format (transcription.json). For backward compatibility, we also
    # understand the legacy exported format:
    #   <outputs>/<video_name>/metadata/metadata.jsonl
    #   <outputs>/<video_name>/vad_segments/*.wav
    #
    # As outputs are not per-job, we time-filter *marker files* (transcription.json or metadata.jsonl)
    # and include only audio referenced by those markers.
    def _mtime_in_window(p: Path) -> bool:
        try:
            mtime = float(p.stat().st_mtime)
        except OSError:
            return False
        if start_ts is not None and mtime < start_ts:
            return False
        if end_ts is not None and mtime > end_ts:
            return False
        return True

    def _iter_exported_videos() -> list[tuple[str, Path, list[dict]]]:
        """
        Returns list of (video_folder_name, video_dir, transcription_rows)
        where transcription_rows is a list of {file_name, transcription}.
        """
        # Preferred: job-scoped exported outputs.
        if job_outputs_dir and job_outputs_dir.exists() and job_outputs_dir.is_dir():
            results: list[tuple[str, Path, list[dict]]] = []
            for tjson in job_outputs_dir.rglob("transcription.json"):
                if not tjson.is_file():
                    continue
                video_dir = tjson.parent
                try:
                    data = json.loads(tjson.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                rows: list[dict] = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    fn = item.get("file_name")
                    if not fn or not isinstance(fn, str):
                        continue
                    rows.append({"file_name": fn, "transcription": item.get("transcription", "")})
                if rows:
                    results.append((video_dir.name, video_dir, rows))
            if results:
                return results

        if not outputs_dir or not outputs_dir.exists() or not outputs_dir.is_dir():
            return []

        results: list[tuple[str, Path, list[dict]]] = []

        # New format: <video_dir>/transcription.json
        for tjson in outputs_dir.rglob("transcription.json"):
            if not tjson.is_file() or not _mtime_in_window(tjson):
                continue
            video_dir = tjson.parent
            try:
                data = json.loads(tjson.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, list):
                continue
            rows: list[dict] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                fn = item.get("file_name")
                if not fn or not isinstance(fn, str):
                    continue
                rows.append({"file_name": fn, "transcription": item.get("transcription", "")})
            if rows:
                results.append((video_dir.name, video_dir, rows))

        if results:
            return results

        # Legacy exported format: <video_dir>/metadata/metadata.jsonl + <video_dir>/vad_segments/*.wav
        for mjsonl in outputs_dir.rglob("metadata/metadata.jsonl"):
            if not mjsonl.is_file() or not _mtime_in_window(mjsonl):
                continue
            video_dir = mjsonl.parent.parent
            rows: list[dict] = []
            try:
                with open(mjsonl, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        fn = obj.get("file_name")
                        if not fn or not isinstance(fn, str):
                            continue
                        rows.append({"file_name": fn, "transcription": obj.get("transcription", "")})
            except OSError:
                continue
            if rows:
                results.append((video_dir.name, video_dir, rows))

        return results

    exported = _iter_exported_videos()
    if not exported:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No exported outputs found for this job (expected outputs/<video>/transcription.json). Re-run the pipeline or ensure export is enabled.",
        )

    download_dir = Path(tempfile.gettempdir()) / "pipeline_downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    # Use a unique ZIP name per request to avoid corruption if multiple downloads happen concurrently.
    import uuid
    zip_path = download_dir / f"job_{job_id}_processed_{uuid.uuid4().hex}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for video_name, video_dir, rows in exported:
            folder = video_name
            # Write transcription.json into the ZIP root folder for that video.
            transcription_arc = f"{folder}/transcription.json"
            if transcription_arc not in used:
                used.add(transcription_arc)
                zf.writestr(transcription_arc, json.dumps(rows, ensure_ascii=False, indent=2))

            for item in rows:
                fn = item.get("file_name")
                if not fn or not isinstance(fn, str):
                    continue
                # New format stores audio at <video_dir>/<file_name>
                audio_path = video_dir / fn
                if not audio_path.exists() and (video_dir / "vad_segments" / fn).exists():
                    # Legacy exported format stored audio under vad_segments/
                    audio_path = video_dir / "vad_segments" / fn
                if not audio_path.exists() or not audio_path.is_file():
                    continue
                if audio_path.suffix.lower() != ".wav":
                    continue
                arcname = f"{folder}/{Path(fn).name}"
                if arcname in used:
                    continue
                used.add(arcname)
                try:
                    zf.write(audio_path, arcname)
                except OSError:
                    continue

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"job_{job_id}_processed.zip",
        background=BackgroundTask(lambda: os.path.exists(zip_path) and os.remove(zip_path)),
    )


@router.post("/{job_id}/cancel")
async def cancel_pipeline_job(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager),
    scheduler: BackgroundJobScheduler = Depends(get_scheduler)
):
    """
    Cancel a running pipeline job.
    """
    # Check ownership
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Cancel job
    result = await scheduler.cancel_and_cleanup(job_id, current_user.id)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['error']
        )

    return result


@router.post("/{job_id}/retry", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def retry_pipeline_job(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager),
    scheduler: BackgroundJobScheduler = Depends(get_scheduler)
):
    """
    Retry a failed pipeline job.

    Creates a new job with the same parameters.
    Note: Current pipeline doesn't support resume from step,
    so this performs a full restart.
    """
    # Get original job
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Check ownership
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Can only retry failed jobs
    if job.status != 'failed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only retry failed jobs. Current status: {job.status}"
        )

    # Create new job with same parameters
    result = await scheduler.schedule_and_execute(
        user_id=current_user.id,
        source_type=job.source_type,
        source_value=job.source_value,
        file_count=job.file_count or 0,
        total_size=job.total_size_bytes or 0
    )

    # Get new job
    new_job = manager.get_job(result['job_id'])

    return PipelineResponse(
        id=new_job.id,
        user_id=new_job.user_id,
        status=new_job.status,
        source_type=new_job.source_type,
        source_value=new_job.source_value,
        error_message=new_job.error_message,
        last_successful_step=new_job.last_successful_step,
        file_count=new_job.file_count,
        total_size_bytes=new_job.total_size_bytes,
        created_at=new_job.created_at.isoformat() if new_job.created_at else None,
        started_at=new_job.started_at.isoformat() if new_job.started_at else None,
        completed_at=new_job.completed_at.isoformat() if new_job.completed_at else None
    )


@router.delete("/{job_id}")
def delete_pipeline_job(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Delete a pipeline job.

    Can only delete non-running jobs.
    """
    # Check ownership
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Delete job
    deleted = manager.delete_job(job_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete running job"
        )

    return {"message": "Job deleted successfully"}


@router.get("/{job_id}/logs")
def get_pipeline_logs(
    job_id: int,
    lines: int = 100,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Get logs for a pipeline job.

    Returns last N lines from stored output.
    """
    # Check ownership
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get error traceback if available
    error_traceback = job.error_traceback or "No errors"

    return {
        'job_id': job_id,
        'status': job.status,
        'error_message': job.error_message,
        'error_traceback': error_traceback,
        'last_successful_step': job.last_successful_step,
    }


@router.post("/files/upload")
async def upload_files_for_local_source(
    files: List[UploadFile] = File(..., description="Audio files to process"),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    manager: PipelineJobManager = Depends(get_pipeline_manager)
):
    """
    Upload files for local source type.

    Validates file count (max 5) and total size (max 2GB).
    Files are stored in user's temp directory.
    """
    # Validate file count
    if len(files) > settings.max_file_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum: {settings.max_file_count}"
        )

    # Convert to file paths for validation
    from pathlib import Path
    from backend.utils.file_utils import save_uploaded_file

    # Get temp directory for this upload session
    from backend.database import get_job_temp_dir
    temp_dir = get_job_temp_dir(current_user.id, 0)  # Use job_id 0 for uploads

    # Save uploaded files
    uploaded_paths = []
    total_size = 0

    for uploaded_file in files:
        # Validate file extension
        if uploaded_file.filename:
            ext = Path(uploaded_file.filename).suffix.lower()
            if ext not in ALLOWED_AUDIO_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {ext}"
                )

        # Read and save file
        content = await uploaded_file.read()
        file_size = len(content)
        total_size += file_size

        file_path = save_uploaded_file(
            current_user.id,
            0,
            uploaded_file.filename or "upload",
            content,
            temp_dir
        )

        uploaded_paths.append(file_path)

    # Validate total size
    max_size = settings.max_input_size_mb * 1024 * 1024
    if total_size > max_size:
        # Cleanup uploaded files
        import shutil
        for file_path in uploaded_paths:
            if file_path.exists():
                file_path.unlink()

        size_mb = total_size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Files too large ({size_mb:.1f}MB). Maximum: {max_mb}MB"
        )

    return {
        'success': True,
        'file_count': len(uploaded_paths),
        'total_size_bytes': total_size,
        'temp_dir': str(temp_dir)
    }
