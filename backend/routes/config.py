"""
Config routes.
Get/save user configuration.
Sensitive values (tokens) are masked before sending to frontend.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.config_service import (
    save_user_config,
    get_user_config_dict_masked,
    delete_user_config,
    reset_user_config,
    validate_config_dict,
    ALLOWED_CONFIG_KEYS,
    get_huggingface_token,
    save_huggingface_token,
    delete_huggingface_token
)
from backend.routes.auth import require_auth
from backend.models.user import User


router = APIRouter(prefix="/api/config", tags=["config"])


# Pydantic models
class ConfigRequest(BaseModel):
    """Config update request (partial update supported)."""
    huggingface_repo_id: Optional[str] = None
    huggingface_token: Optional[str] = None
    huggingface_private: Optional[bool] = None
    download_max_workers: Optional[int] = None
    download_scrape_enabled: Optional[bool] = None
    download_scrape_interval_minutes: Optional[int] = None
    download_sources: Optional[dict] = None
    noise_reduction_enabled: Optional[bool] = None
    filtering_enabled: Optional[bool] = None


class HuggingFaceTokenRequest(BaseModel):
    """HF token update request."""
    token: str = ...  # Required


class ConfigResponse(BaseModel):
    """Config response (sensitive values masked)."""
    huggingface: Dict[str, Any]
    download: Dict[str, Any]
    noise_reduction: Dict[str, bool]
    filtering: Dict[str, bool]


@router.get("", response_model=Dict)
def get_config(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get current user configuration.

    Returns full config dict with sensitive values masked.
    Tokens are NEVER returned in plain text.
    """
    config = get_user_config_dict_masked(current_user.id, db)

    # Convert nested keys to match frontend expectations
    return {
        'huggingface': config.get('huggingface', {}),
        'download': config.get('download', {}),
        'noise_reduction': config.get('noise_reduction', {}),
        'filtering': config.get('filtering', {}),
    }


@router.put("")
def save_config(
    config_request: ConfigRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Save user configuration (partial update supported).

    Validates each key-value pair before saving.
    Tokens are encrypted before storage.
    """
    # Build config dict from request
    config_data = {}

    if config_request.huggingface_repo_id is not None:
        config_data['huggingface.repo_id'] = config_request.huggingface_repo_id

    if config_request.huggingface_token is not None:
        config_data['huggingface.token'] = config_request.huggingface_token

    if config_request.huggingface_private is not None:
        config_data['huggingface.private'] = config_request.huggingface_private

    if config_request.download_max_workers is not None:
        config_data['download.max_workers'] = config_request.download_max_workers

    if config_request.download_scrape_enabled is not None:
        config_data['download.scrape.enabled'] = config_request.download_scrape_enabled

    if config_request.download_scrape_interval_minutes is not None:
        config_data['download.scrape.interval_minutes'] = config_request.download_scrape_interval_minutes

    if config_request.download_sources is not None:
        config_data['download.sources'] = config_request.download_sources

    if config_request.noise_reduction_enabled is not None:
        config_data['noise_reduction.enabled'] = config_request.noise_reduction_enabled

    if config_request.filtering_enabled is not None:
        config_data['filtering.enabled'] = config_request.filtering_enabled

    # Validate
    errors = validate_config_dict(config_data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors}
        )

    # Save
    save_user_config(current_user.id, config_data, db)

    return {"message": "Configuration saved successfully"}


@router.delete("")
def reset_config(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Reset user configuration to defaults.

    Deletes all user config entries.
    """
    reset_user_config(current_user.id, db)
    return {"message": "Configuration reset to defaults"}


@router.get("/huggingface/token")
def get_hf_token_endpoint(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get HuggingFace token (masked).

    Token is masked: "********" or "ab****cd"
    Never returns the full token.
    """
    token = get_huggingface_token(current_user.id, db, masked=True)

    if not token:
        return {"token": None}

    return {"token": token}


@router.put("/huggingface/token")
def save_hf_token_endpoint(
    token_request: HuggingFaceTokenRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Save HuggingFace token (encrypted on server).

    Token is encrypted with AES-256 before storage.
    """
    save_huggingface_token(current_user.id, token_request.token, db)
    return {"message": "HuggingFace token saved"}


@router.delete("/huggingface/token")
def delete_hf_token_endpoint(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Delete stored HuggingFace token.
    """
    delete_huggingface_token(current_user.id, db)
    return {"message": "HuggingFace token deleted"}