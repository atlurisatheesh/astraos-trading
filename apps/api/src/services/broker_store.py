"""AstraOS Services — Broker credential persistence + session restore.

Credentials are Fernet-encrypted with a key derived from JWT_SECRET_KEY.
On server restart (or broker-session expiry) the stored credentials are
used to transparently re-login, so Angel One monitoring keeps working
without the user re-entering API key / TOTP secret.
"""

import base64
import hashlib
import json

import structlog
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.broker import BrokerCredential

logger = structlog.get_logger()


def _fernet() -> Fernet:
    settings = get_settings()
    digest = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_payload(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_payload(token: str) -> dict:
    return json.loads(_fernet().decrypt(token.encode()).decode())


async def save_credentials(db: AsyncSession, user_id, broker: str, creds: dict) -> None:
    """Upsert encrypted broker credentials for a user."""
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.broker == broker.lower(),
        )
    )
    row = result.scalar_one_or_none()
    payload = encrypt_payload(creds)
    if row:
        row.encrypted_payload = payload
    else:
        db.add(BrokerCredential(user_id=user_id, broker=broker.lower(), encrypted_payload=payload))
    await db.commit()
    logger.info("Broker credentials persisted", broker=broker)


async def load_credentials(db: AsyncSession, user_id, broker: str) -> dict | None:
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.broker == broker.lower(),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    try:
        return decrypt_payload(row.encrypted_payload)
    except Exception as e:
        logger.error("Failed to decrypt broker credentials", broker=broker, error=str(e))
        return None


async def delete_credentials(db: AsyncSession, user_id, broker: str) -> None:
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.broker == broker.lower(),
        )
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()


async def restore_session(db: AsyncSession, user_id, broker_name: str):
    """Re-login to a broker using stored credentials. Returns adapter or None."""
    creds = await load_credentials(db, user_id, broker_name)
    if not creds:
        return None
    try:
        from ..broker import get_broker, BrokerCredentials

        broker = get_broker(broker_name)
        credentials = BrokerCredentials(
            api_key=creds.get("api_key", ""),
            api_secret=creds.get("api_secret", ""),
            client_id=creds.get("client_id", ""),
            password=creds.get("password", ""),
            totp_secret=creds.get("totp_secret", ""),
            access_token=creds.get("access_token", ""),
            request_token=creds.get("request_token", ""),
            extras=creds.get("extras", {}),
        )
        result = await broker.login(credentials)
        if result.get("status") == "success":
            logger.info("Broker session auto-restored", broker=broker_name)
            return broker
        logger.warning("Broker auto-relogin failed", broker=broker_name, result=result)
    except Exception as e:
        logger.error("Broker session restore error", broker=broker_name, error=str(e))
    return None
