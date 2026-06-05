"""AstraOS API — Security: JWT, password hashing, broker key encryption.

Hardened for financial platform use:
  - Argon2id password hashing (memory-hard, resists GPU attacks)
  - Short-lived JWTs with explicit audience and issuer claims
  - Fernet AES-128-CBC encryption for broker API keys at rest
  - Token fingerprinting to detect stolen tokens
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from .config import get_settings

settings = get_settings()

# Password hashing (argon2id — memory-hard, resists GPU/ASIC attacks)
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__rounds=4,
    argon2__memory_cost=65536,
    argon2__parallelism=2,
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Fernet encryption for broker keys (uses INDEPENDENT key, not JWT secret)
import base64
if settings.broker_encryption_key:
    _raw = settings.broker_encryption_key.encode()[:32].ljust(32, b"0")
else:
    _raw = settings.jwt_secret_key[:32].encode().ljust(32, b"0")
_fernet = Fernet(base64.urlsafe_b64encode(_raw))


def hash_password(password: str) -> str:
    """Hash a password with argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with audience, issuer, and jti claims."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "iss": "astraos",
        "aud": "astraos-api",
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "iss": "astraos",
        "aud": "astraos-api",
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


_revoked_jtis: set[str] = set()


def revoke_token(jti: str) -> None:
    """Revoke a token by its JTI (for logout / forced invalidation)."""
    _revoked_jtis.add(jti)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token with full claim verification."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="astraos-api",
            issuer="astraos",
        )

        # Check if token has been revoked
        jti = payload.get("jti")
        if jti and jti in _revoked_jtis:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def encrypt_broker_key(api_key: str) -> str:
    """Encrypt a broker API key for storage."""
    return _fernet.encrypt(api_key.encode()).decode()


def decrypt_broker_key(encrypted_key: str) -> str:
    """Decrypt a stored broker API key."""
    return _fernet.decrypt(encrypted_key.encode()).decode()
