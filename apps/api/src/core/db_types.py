"""Database-agnostic column types that work on both PostgreSQL and SQLite."""

import os
from sqlalchemy import JSON, String, Text
from sqlalchemy.types import TypeDecorator
import uuid


def _is_sqlite() -> bool:
    url = os.getenv("DATABASE_URL", "")
    return url.startswith("sqlite") or not url


# JSONB → JSON (functionally equivalent for Python dicts)
JSONB = JSON

# UUID — store as string (works on both SQLite and PostgreSQL)
class UUID(TypeDecorator):
    """Platform-independent UUID type. Uses String(36) on SQLite, native UUID on PostgreSQL."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value))


# ARRAY(Integer) → JSON list (SQLite doesn't support ARRAY)
class _ARRAY_JSON(TypeDecorator):
    """Store arrays as JSON lists. Portable across all databases."""
    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__()  # ignore element type

    def process_bind_param(self, value, dialect):
        if value is None:
            return "[]"
        import json
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        import json
        try:
            return json.loads(value)
        except Exception:
            return []


def ARRAY_JSON(element_type=None):
    return _ARRAY_JSON()
