"""
File upload routes.
Upload files to temp directory, validate size/count, cleanup.
"""

from typing import List, Optional
from pathlib import Path
import shutil
import os

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from backend.database import get_db, get_job_temp_dir
from backend.routes.auth import require_auth
from backend.models.user import User
from backend.config import settings
from backend.utils.file_utils import (
    ALLOWED_AUDIO_EXTENSIONS,
    validate_file_batch,
    save_uploaded_file,
    cleanup_job_temp
)


router = APIRouter(prefix="/api/files", tags=["files"])

# Max input size: 2GB
MAX_INPUT_SIZE_BYTES = settings.max_input_size_mb * 1024 * 1024

# Max files per job
MAX_FILE_COUNT = settings.max_file_count


class FileUploadResponse(BaseModel):
    """Response for file upload."""
    success: bool
    file_count: int
    total_size_bytes: int
    total_size_mb: float
    files: List[str]
    temp_dir: Optional[str] = None
    error: Optional[str] = None


class FileListResponse(BaseModel):
    """Response for listing uploaded files."""
    files: List[dict]


@router.post("/upload", response_model=FileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(..., description="Audio files to upload"),
    job_id: Optional[int] = Query(None, description="Associated job ID (optional)"),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Upload audio files to user's temp directory.

    Validates:
    - File count (max 5)
    - Total size (max 2GB)
    - File extensions (must be audio)

    Files are stored in data/users/{user_id}/tmp/job_{job_id}/
    """
    # Check file count limit
    if len(files) > MAX_FILE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum: {MAX_FILE_COUNT}"
        )

    # Determine temp directory
    if job_id is not None:
        temp_dir = get_job_temp_dir(current_user.id, job_id)
    else:
        # Use session_id=0 for general uploads not tied to a job yet
        temp_dir = get_job_temp_dir(current_user.id, 0)

    # Validate and save files
    uploaded_files = []
    total_size = 0
    errors = []

    for uploaded_file in files:
        # Validate filename
        if not uploaded_file.filename:
            errors.append("Missing filename")
            continue

        filename = uploaded_file.filename
        file_ext = Path(filename).suffix.lower()

        # Validate file extension
        if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
            errors.append(f"Invalid file type: {filename}")
            continue

        # Read file content
        try:
            content = await uploaded_file.read()
            file_size = len(content)

            # Check individual file size (optional, could add max per-file limit)
            if file_size > MAX_INPUT_SIZE_BYTES:
                errors.append(f"File too large: {filename}")
                continue

            # Save file
            file_path = save_uploaded_file(
                current_user.id,
                job_id or 0,
                filename,
                content,
                temp_dir
            )

            uploaded_files.append({
                'filename': filename,
                'path': str(file_path),
                'size': file_size,
                'extension': file_ext
            })

            total_size += file_size

        except Exception as e:
            errors.append(f"Error processing {filename}: {str(e)}")
            continue

    # Validate total size
    if total_size > MAX_INPUT_SIZE_BYTES:
        # Cleanup all uploaded files if total exceeds limit
        for file_info in uploaded_files:
            try:
                os.unlink(file_info['path'])
            except Exception:
                pass

        total_size_mb = total_size / (1024 * 1024)
        max_mb = MAX_INPUT_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Total size too large ({total_size_mb:.1f}MB). Maximum: {max_mb}MB"
        )

    # Check for any errors
    if errors:
        # Cleanup on error
        for file_info in uploaded_files:
            try:
                os.unlink(file_info['path'])
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors, "uploaded": len(uploaded_files)}
        )

    return FileUploadResponse(
        success=True,
        file_count=len(uploaded_files),
        total_size_bytes=total_size,
        total_size_mb=total_size / (1024 * 1024),
        files=[f['filename'] for f in uploaded_files],
        temp_dir=str(temp_dir)
    )


@router.get("/temp/{job_id}", response_model=FileListResponse)
def list_temp_files(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    List uploaded files in temp directory for a job.

    Args:
        job_id: Job ID

    Returns:
        List of uploaded files with metadata
    """
    temp_dir = get_job_temp_dir(current_user.id, job_id)

    if not temp_dir.exists():
        return FileListResponse(files=[])

    files = []
    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            files.append({
                'filename': file_path.name,
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'extension': file_path.suffix.lower(),
            })

    return FileListResponse(files=files)


@router.get("/temp/{job_id}/size")
def get_temp_files_size(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get total size of uploaded files in temp directory.

    Args:
        job_id: Job ID

    Returns:
        Total size in bytes and MB
    """
    temp_dir = get_job_temp_dir(current_user.id, job_id)

    if not temp_dir.exists():
        return {
            'total_size_bytes': 0,
            'total_size_mb': 0.0,
            'file_count': 0
        }

    total_size = 0
    file_count = 0

    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            total_size += file_path.stat().st_size
            file_count += 1

    return {
        'total_size_bytes': total_size,
        'total_size_mb': total_size / (1024 * 1024),
        'file_count': file_count
    }


@router.delete("/temp/{job_id}")
def clear_temp_files(
    job_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Clear uploaded files from temp directory.

    Args:
        job_id: Job ID

    Returns:
        Success message
    """
    temp_dir = get_job_temp_dir(current_user.id, job_id)

    if not temp_dir.exists():
        return {"message": "No files to clear"}

    # Delete temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Recreate directory
    temp_dir.mkdir(parents=True, exist_ok=True)

    return {
        "message": f"Temp files cleared for job {job_id}",
        "files_deleted": True
    }


@router.delete("/temp/{job_id}/file/{filename}")
def delete_temp_file(
    job_id: int,
    filename: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Delete a specific uploaded file from temp directory.

    Args:
        job_id: Job ID
        filename: Name of file to delete

    Returns:
        Success message
    """
    temp_dir = get_job_temp_dir(current_user.id, job_id)

    # Sanitize filename to prevent path traversal
    safe_filename = "".join(c for c in filename if c.isalnum() or c in '._-')

    file_path = temp_dir / safe_filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Delete file
    os.unlink(file_path)

    return {
        "message": f"File {filename} deleted",
        "file_deleted": True
    }


@router.get("/validation")
def get_upload_limits():
    """
    Get upload limits for frontend validation.

    Returns:
        Max file count, max total size, allowed extensions
    """
    return {
        "max_file_count": MAX_FILE_COUNT,
        "max_size_bytes": MAX_INPUT_SIZE_BYTES,
        "max_size_mb": MAX_INPUT_SIZE_BYTES / (1024 * 1024),
        "allowed_extensions": list(ALLOWED_AUDIO_EXTENSIONS),
        "allowed_extensions_display": ", ".join(ALLOWED_AUDIO_EXTENSIONS),
    }