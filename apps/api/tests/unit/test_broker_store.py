"""Tests — broker credential persistence + background sync snapshot."""

import uuid

import pytest

from src.services.broker_store import (
    encrypt_payload,
    decrypt_payload,
    save_credentials,
    load_credentials,
    delete_credentials,
)
from src.scheduler.jobs import get_broker_snapshots


class TestEncryption:
    def test_roundtrip(self):
        data = {"api_key": "k123", "totp_secret": "S3CR3T", "extras": {"pin": "0000"}}
        token = encrypt_payload(data)
        assert token != ""
        assert "k123" not in token  # never plaintext
        assert decrypt_payload(token) == data

    def test_tampered_token_fails(self):
        token = encrypt_payload({"a": 1})
        with pytest.raises(Exception):
            decrypt_payload(token[:-4] + "AAAA")


@pytest.mark.asyncio
class TestCredentialStore:
    async def test_save_load_delete(self, db_session):
        user_id = uuid.uuid4()
        creds = {"api_key": "key", "client_id": "C123", "password": "pin", "totp_secret": "T"}

        await save_credentials(db_session, user_id, "angel", creds)
        loaded = await load_credentials(db_session, user_id, "angel")
        assert loaded["client_id"] == "C123"

        # Upsert overwrites
        await save_credentials(db_session, user_id, "angel", {**creds, "client_id": "C999"})
        loaded = await load_credentials(db_session, user_id, "angel")
        assert loaded["client_id"] == "C999"

        await delete_credentials(db_session, user_id, "angel")
        assert await load_credentials(db_session, user_id, "angel") is None

    async def test_load_missing_returns_none(self, db_session):
        assert await load_credentials(db_session, uuid.uuid4(), "kite") is None


def test_snapshot_getter_returns_copy():
    snaps = get_broker_snapshots()
    assert isinstance(snaps, dict)
    snaps["injected"] = {}
    assert "injected" not in get_broker_snapshots()
