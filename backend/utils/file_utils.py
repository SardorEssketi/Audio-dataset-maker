"""
User file utilities.
File validation, size calculation, cleanup.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import os
import shutil

from backend.database import get_user_dir, get_job_temp_dir


# Allowed audio file extensions
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.opus'}


def validate_file(file_path: Path) -> Optional[str]:
    """
    Validate a single audio file.

    Args:
        file_path: Path to file

    Returns:
        None if valid, error message otherwise
    """
    if not file_path.exists():
        return "File does not exist"

    if not file_path.is_file():
        return "Path is not a file"

    if file_path.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        return f"Invalid file type. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"

    return None


def validate_file_size(file_path: Path, max_size_bytes: int) -> Optional[str]:
    """
    Validate file size against limit.

    Args:
        file_path: Path to file
        max_size_bytes: Maximum allowed size in bytes

    Returns:
        None if valid, error message otherwise
    """
    size = file_path.stat().st_size

    if size > max_size_bytes:
        size_mb = size / (1024 * 1024)
        max_mb = max_size_bytes / (1024 * 1024)
        return f"File too large ({size_mb:.1f}MB). Max: {max_mb}MB"

    return None


def validate_file_batch(
    file_paths: List[Path],
    max_count: int,
    max_total_size_bytes: int
) -> Tuple[bool, List[str], int]:
    """
    Validate a batch of files.

    Args:
        file_paths: List of file paths
        max_count: Maximum allowed file count
        max_total_size_bytes: Maximum total size in bytes

    Returns:
        (is_valid, error_messages, total_size_bytes)
    """
    errors = []
    total_size = 0

    if len(file_paths) > max_count:
        errors.append(f"Too many files ({len(file_paths)}). Max: {max_count}")
        return False, errors, 0

    for file_path in file_paths:
        # Validate file existence and type
        file_error = validate_file(file_path)
        if file_error:
            errors.append(f"{file_path.name}: {file_error}")
            continue

        # Validate size
        size_error = validate_file_size(file_path, max_total_size_bytes)
        if size_error:
            errors.append(f"{file_path.name}: {size_error}")
            continue

        total_size += file_path.stat().st_size

    # Check total size
    if total_size > max_total_size_bytes:
        size_mb = total_size / (1024 * 1024)
        max_mb = max_total_size_bytes / (1024 * 1024)
        errors.append(f"Total size too large ({size_mb:.1f}MB). Max: {max_mb}MB")

    is_valid = len(errors) == 0
    return is_valid, errors, total_size


def save_uploaded_file(
    user_id: int,
    job_id: int,
    filename: str,
    content: bytes,
    job_temp_dir: Optional[Path] = None
) -> Path:
    """
    Save uploaded file to user's temp directory.

    Args:
        user_id: User ID
        job_id: Job ID
        filename: Original filename
        content: File content
        job_temp_dir: Optional specific temp directory

    Returns:
        Path to saved file
    """
    if job_temp_dir is None:
        job_temp_dir = get_job_temp_dir(user_id, job_id)

    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in '._-')
    if not safe_filename:
        safe_filename = "upload"

    # Ensure unique filename
    file_path = job_temp_dir / safe_filename
    counter = 1
    while file_path.exists():
        stem = Path(safe_filename).stem
        suffix = Path(safe_filename).suffix
        file_path = job_temp_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    file_path.write_bytes(content)
    return file_path


def cleanup_job_temp(user_id: int, job_id: int) -> None:
    """
    Clean up temporary files for a specific job.
    """
    job_temp = get_job_temp_dir(user_id, job_id)

    if job_temp.exists():
        shutil.rmtree(job_temp, ignore_errors=True)


def get_file_count_in_dir(directory: Path) -> int:
    """
    Count audio files in a directory.
    """
    if not directory.exists():
        return 0

    count = 0
    for file_path in directory.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
            count += 1

    return count


def get_directory_size(directory: Path) -> int:
    """
    Get total size of a directory in bytes.
    """
    if not directory.exists():
        return 0

    total_size = 0
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size

    return total_size


def create_user_config_yaml(user_id: int, config_dict: dict) -> Path:
    """
    Create temporary config file for pipeline execution.

    Args:
        user_id: User ID
        config_dict: Full config dict with user-specific paths

    Returns:
        Path to created config file
    """
    import yaml

    user_dir = get_user_dir(user_id, create=True)
    config_path = user_dir / 'tmp' / 'config.yaml'
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    return config_path