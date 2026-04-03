"""
Authentication service.

Responsibilities:
- Password hashing / verification
- JWT access token creation / validation
- Encryption / decryption of sensitive config values
- User lookup / authentication / creation
"""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, ExpiredSignatureError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import get_config_encryption_key, settings
from backend.models.user import User

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALGORITHM = "HS256"


class AuthError(Exception):
    """Base authentication service exception."""


class TokenValidationError(AuthError):
    """Raised when a JWT token is invalid."""


class TokenExpiredError(TokenValidationError):
    """Raised when a JWT token has expired."""


class EncryptionUnavailableError(AuthError):
    """Raised when encryption key is not configured."""


class EncryptionError(AuthError):
    """Raised when encryption/decryption fails."""


class UserAlreadyExistsError(AuthError):
    """Raised when username or email already exists."""


def utc_now() -> datetime:
    """
    Return timezone-aware UTC datetime.
    """
    return datetime.now(timezone.utc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        logger.exception("Password verification failed unexpectedly.")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    """
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token.

    Args:
        data: Payload data, usually including {'sub': '<user_id>'}
        expires_delta: Optional expiration delta

    Returns:
        Encoded JWT string

    Raises:
        ValueError: If payload is invalid
    """
    if "sub" not in data or data["sub"] in (None, ""):
        raise ValueError("JWT payload must include a non-empty 'sub' field.")

    expire = utc_now() + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    to_encode = data.copy()
    to_encode.update(
        {
            "exp": expire,
            "iat": utc_now(),
        }
    )

    return jwt.encode(to_encode, settings.secret_key, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT access token.

    Args:
        token: JWT access token

    Returns:
        Decoded payload

    Raises:
        TokenExpiredError: If token is expired
        TokenValidationError: If token is invalid or malformed
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])

        sub = payload.get("sub")
        if sub in (None, ""):
            raise TokenValidationError("Token payload missing 'sub'.")

        return payload

    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired.") from exc
    except JWTError as exc:
        raise TokenValidationError("Invalid access token.") from exc


def _build_fernet_from_key(key: str) -> Fernet:
    """
    Build a Fernet instance from a configured key.

    Accepted formats:
    - Standard Fernet key (URL-safe base64-encoded 32-byte key, usually 44 chars)
    - Raw 32-byte string value

    Args:
        key: Encryption key from config

    Returns:
        Fernet instance

    Raises:
        EncryptionError: If key format is invalid
    """
    key = key.strip()
    if not key:
        raise EncryptionError("Encryption key is empty.")

    # Case 1: already a valid Fernet key
    try:
        key_bytes = key.encode("utf-8")
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) == 32:
            return Fernet(key_bytes)
    except (binascii.Error, ValueError):
        pass

    # Case 2: raw 32-byte string, convert to Fernet format
    raw_bytes = key.encode("utf-8")
    if len(raw_bytes) == 32:
        return Fernet(base64.urlsafe_b64encode(raw_bytes))

    raise EncryptionError(
        "Invalid encryption key format. "
        "Provide a valid Fernet key or a raw 32-byte key."
    )


def get_fernet() -> Fernet:
    """
    Get Fernet cipher instance for encryption.

    Returns:
        Fernet instance

    Raises:
        EncryptionUnavailableError: If encryption key is not configured
        EncryptionError: If encryption key format is invalid
    """
    key = get_config_encryption_key()
    if not key:
        raise EncryptionUnavailableError("Encryption key is not configured.")

    return _build_fernet_from_key(key)


def encrypt_token(token: str) -> str:
    """
    Encrypt a sensitive token for storage.

    Args:
        token: Plain text token

    Returns:
        Encrypted token string

    Raises:
        EncryptionUnavailableError: If encryption is unavailable
        EncryptionError: If encryption fails
    """
    try:
        fernet = get_fernet()
        return fernet.encrypt(token.encode("utf-8")).decode("utf-8")
    except EncryptionUnavailableError:
        raise
    except EncryptionError:
        raise
    except Exception as exc:
        logger.exception("Failed to encrypt sensitive token.")
        raise EncryptionError("Token encryption failed.") from exc


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a stored encrypted token.

    Args:
        encrypted_token: Encrypted token string

    Returns:
        Plain text token

    Raises:
        EncryptionUnavailableError: If encryption is unavailable
        EncryptionError: If decryption fails
    """
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except EncryptionUnavailableError:
        raise
    except InvalidToken as exc:
        raise EncryptionError("Encrypted token is invalid or corrupted.") from exc
    except EncryptionError:
        raise
    except Exception as exc:
        logger.exception("Failed to decrypt sensitive token.")
        raise EncryptionError("Token decryption failed.") from exc


def mask_token(token: str) -> str:
    """
    Mask a token for display to the user.
    Never returns the full token to frontend.

    Args:
        token: Plain text token

    Returns:
        Masked token string
    """
    if not token:
        return "****"
    if len(token) <= 4:
        return "****"
    return token[:2] + "*" * (len(token) - 4) + token[-2:]


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get user by username.
    """
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get user by email.
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get user by ID.
    """
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username/email and password.

    Args:
        db: Database session
        username: Username or email
        password: Plain text password

    Returns:
        Authenticated User if valid, otherwise None
    """
    user = get_user_by_username(db, username)

    if not user:
        user = get_user_by_email(db, username)

    if not user:
        return None

    if not user.is_active:
        logger.info("Authentication rejected for inactive user: %s", user.username)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_user(
    db: Session,
    username: str,
    email: Optional[str],
    password: str,
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        username: Username, must be unique
        email: Email, must be unique if provided
        password: Plain text password

    Returns:
        Created User object

    Raises:
        UserAlreadyExistsError: If username/email already exists
        ValueError: If input is invalid
    """
    username = username.strip()
    email = email.strip() if email else None

    if not username:
        raise ValueError("Username cannot be empty.")
    if not password:
        raise ValueError("Password cannot be empty.")

    existing_user = get_user_by_username(db, username)
    if existing_user:
        raise UserAlreadyExistsError("Username already exists.")

    if email:
        existing_email = get_user_by_email(db, email)
        if existing_email:
            raise UserAlreadyExistsError("Email already exists.")

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    except IntegrityError as exc:
        db.rollback()
        logger.warning("User creation failed due to integrity error: %s", exc)
        raise UserAlreadyExistsError("Username or email already exists.") from exc

    except Exception:
        db.rollback()
        logger.exception("Unexpected error during user creation.")
        raise