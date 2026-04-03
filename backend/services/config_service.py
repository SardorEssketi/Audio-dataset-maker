"""
Config service.
Manages user-specific configuration with token encryption.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from sqlalchemy.orm import Session

import yaml

from backend.models.config import UserConfig
from backend.services.auth_service import encrypt_token, decrypt_token, mask_token
from backend.database import get_user_config_path


# Config keys that should be encrypted
ENCRYPTED_KEYS = [
    'huggingface.token',
]

# Config keys allowed for frontend modification
ALLOWED_CONFIG_KEYS = [
    # HuggingFace
    'huggingface.repo_id',
    'huggingface.private',
    'huggingface.token',

    # Download
    'download.max_workers',
    'download.scrape.enabled',
    'download.scrape.interval_minutes',
    'download.sources',

    # Processing
    'noise_reduction.enabled',
    'filtering.enabled',
]


def load_default_config() -> Dict:
    """
    Load default configuration from config/config.yaml.
    Returns base config without user overrides.
    """
    # Project-level config lives at <repo_root>/config/config.yaml
    # This file is under backend/services/, so repo root is 3 parents up.
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"

    if not config_path.exists():
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _set_nested_key(target: Dict, dotted_key: str, value: Any) -> None:
    """
    Set a value into a nested dict using a dotted key, e.g. "download.max_workers".
    Creates intermediate dicts as needed.
    """
    parts = [p for p in str(dotted_key).split('.') if p]
    if not parts:
        return

    cur = target
    for part in parts[:-1]:
        existing = cur.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cur[part] = existing
        cur = existing

    cur[parts[-1]] = value


def expand_dotted_overrides(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a flat override dict with dotted keys into a nested structure.

    Example:
      {"download.max_workers": 4, "download.scrape.enabled": true}
    becomes:
      {"download": {"max_workers": 4, "scrape": {"enabled": true}}}
    """
    result: Dict[str, Any] = {}
    for key, value in (overrides or {}).items():
        if isinstance(key, str) and '.' in key:
            _set_nested_key(result, key, value)
        else:
            result[key] = value
    return result


def validate_config_key(key: str, value: Any) -> Optional[str]:
    """
    Validate a single config key-value pair.

    Args:
        key: Config key (e.g., 'huggingface.repo_id')
        value: Config value

    Returns:
        None if valid, error message otherwise
    """
    # Validate huggingface.repo_id
    if key == 'huggingface.repo_id':
        if not value or not isinstance(value, str):
            return "Repo ID must be a non-empty string"
        if '/' not in str(value):
            return "Repo ID must be in format 'username/repo-name'"

    # Validate huggingface.token
    if key == 'huggingface.token':
        if value and not isinstance(value, str):
            return "Token must be a string"

    # Validate download.max_workers
    if key == 'download.max_workers':
        try:
            workers = int(value)
            if workers < 1 or workers > 10:
                return "Max workers must be between 1 and 10"
        except (TypeError, ValueError):
            return "Max workers must be an integer"

    # Validate download.scrape.interval_minutes
    if key == 'download.scrape.interval_minutes':
        try:
            interval = int(value)
            if interval < 5 or interval > 1440:
                return "Interval must be between 5 and 1440 minutes"
        except (TypeError, ValueError):
            return "Interval must be an integer"

    # Validate download.sources
    if key == 'download.sources':
        if value and not isinstance(value, list):
            return "Sources must be a list"

    # Validate boolean values
    if key in ['noise_reduction.enabled', 'filtering.enabled', 'download.scrape.enabled', 'huggingface.private']:
        if not isinstance(value, bool) and value not in [0, 1, '0', '1', True, False]:
            return f"{key} must be a boolean"

    return None


def validate_config_dict(config: Dict) -> List[str]:
    """
    Validate entire config dictionary.

    Args:
        config: Config dict to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    for key, value in config.items():
        if key not in ALLOWED_CONFIG_KEYS:
            errors.append(f"Unknown config key: {key}")
            continue

        error = validate_config_key(key, value)
        if error:
            errors.append(f"{key}: {error}")

    return errors


def save_user_config(user_id: int, config_data: Dict, db: Session) -> Dict:
    """
    Save user configuration with encryption for sensitive values.

    Args:
        user_id: User ID
        config_data: Config dictionary (may be partial)
        db: Database session

    Returns:
        Updated config dictionary (with any encrypted values)
    """
    result = {}

    for key, value in config_data.items():
        # Validate
        if key not in ALLOWED_CONFIG_KEYS:
            continue

        error = validate_config_key(key, value)
        if error:
            raise ValueError(f"Invalid config value for {key}: {error}")

        # Encrypt sensitive values
        if value is not None and key in ENCRYPTED_KEYS:
            encrypted = encrypt_token(str(value))
            if encrypted:
                value = encrypted

        # Serialize for storage
        if isinstance(value, (dict, list)):
            import json
            storage_value = json.dumps(value)
        else:
            storage_value = str(value) if value is not None else None

        # Upsert
        existing = db.query(UserConfig).filter_by(
            user_id=user_id, config_key=key
        ).first()

        if existing:
            existing.config_value = storage_value
        else:
            new_config = UserConfig(
                user_id=user_id,
                config_key=key,
                config_value=storage_value
            )
            db.add(new_config)

        result[key] = value

    db.commit()
    return result


def get_user_config_dict(user_id: int, db: Session, mask_sensitive: bool = True) -> Dict:
    """
    Get user configuration as dictionary.

    Args:
        user_id: User ID
        db: Database session
        mask_sensitive: If True, mask sensitive values (tokens) instead of decrypting

    Returns:
        Config dictionary with user overrides applied to defaults
    """
    # Load default config
    base_config = load_default_config()

    # Get user overrides from DB
    user_configs = db.query(UserConfig).filter_by(user_id=user_id).all()

    # Apply user overrides
    user_overrides = {}
    for cfg in user_configs:
        key = cfg.config_key
        value = cfg.config_value

        # Decrypt sensitive values or mask them
        if key in ENCRYPTED_KEYS:
            if mask_sensitive:
                # Mask for frontend display
                value = "********"
            else:
                # Decrypt for internal use (pipeline execution)
                decrypted = decrypt_token(value)
                if decrypted:
                    value = decrypted
                else:
                    value = None
        else:
            # Parse JSON for complex values
            try:
                import json
                value = json.loads(value) if value else None
            except (json.JSONDecodeError, TypeError):
                value = value

        user_overrides[key] = value

    # Merge into base config
    return merge_configs(base_config, expand_dotted_overrides(user_overrides))


def get_user_config_dict_with_paths(user_id: int, db: Session, mask_sensitive: bool = True) -> Dict:
    """
    Get user configuration with user-specific paths for pipeline execution.

    Args:
        user_id: User ID
        db: Database session
        mask_sensitive: Mask sensitive values for frontend

    Returns:
        Complete config dict with user paths substituted
    """
    # Get user config (without masking for internal use)
    config = get_user_config_dict(user_id, db, mask_sensitive=False)

    # Substitute user-specific paths
    user_paths = get_user_config_path(user_id)
    existing_paths = config.get('paths') if isinstance(config.get('paths'), dict) else {}
    config['paths'] = {**existing_paths, **user_paths}

    return config


def get_user_config_dict_masked(user_id: int, db: Session) -> Dict:
    """
    Get user configuration for frontend display (sensitive values masked).

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Config dict with masked tokens
    """
    return get_user_config_dict(user_id, db, mask_sensitive=True)


def merge_configs(base: Dict, overrides: Dict) -> Dict:
    """
    Merge user overrides into base config.
    Handles nested structures.
    """
    result = base.copy()

    for key, value in overrides.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # Deep merge for nested dicts
            result[key] = merge_configs(result[key], value)
        else:
            # Direct replacement
            result[key] = value

    return result


def delete_user_config(user_id: int, config_key: str, db: Session) -> None:
    """
    Delete a specific config key for user.

    Args:
        user_id: User ID
        config_key: Config key to delete
        db: Database session
    """
    db.query(UserConfig).filter_by(
        user_id=user_id,
        config_key=config_key
    ).delete()
    db.commit()


def reset_user_config(user_id: int, db: Session) -> None:
    """
    Reset user configuration to defaults.
    Deletes all user config entries.
    """
    db.query(UserConfig).filter_by(user_id=user_id).delete()
    db.commit()


def get_huggingface_token(user_id: int, db: Session, masked: bool = True) -> Optional[str]:
    """
    Get HuggingFace token for a user.

    Args:
        user_id: User ID
        db: Database session
        masked: If True, return masked token (for frontend)

    Returns:
        Decrypted token or masked token, or None if not set
    """
    config = get_user_config_dict(user_id, db, mask_sensitive=False)

    token = config.get('huggingface', {}).get('token')

    if not token:
        return None

    return mask_token(token) if masked else token


def save_huggingface_token(user_id: int, token: str, db: Session) -> None:
    """
    Save HuggingFace token (encrypted).

    Args:
        user_id: User ID
        token: Plain text token to save
        db: Database session
    """
    save_user_config(user_id, {'huggingface.token': token}, db)


def delete_huggingface_token(user_id: int, db: Session) -> None:
    """
    Delete stored HuggingFace token.

    Args:
        user_id: User ID
        db: Database session
    """
    delete_user_config(user_id, 'huggingface.token', db)
