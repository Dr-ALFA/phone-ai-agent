import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import CACHE_TTL_HOURS
from db import create_tables, get_session_factory
from models import SearchCache


def get_cached_payload(query_key: str) -> dict[str, Any] | None:
    session_factory = _ready_session_factory()
    if session_factory is None:
        return None

    try:
        with session_factory() as session:
            cache_entry = session.scalar(
                select(SearchCache).where(SearchCache.query_key == query_key)
            )
            if cache_entry is None or not _is_fresh(cache_entry.created_at):
                return None
            return json.loads(cache_entry.payload_json)
    except SQLAlchemyError:
        return None


def set_cached_payload(query_key: str, payload: dict[str, Any], source: str) -> None:
    session_factory = _ready_session_factory()
    if session_factory is None:
        return

    try:
        with session_factory() as session:
            cache_entry = session.scalar(
                select(SearchCache).where(SearchCache.query_key == query_key)
            )
            if cache_entry is None:
                cache_entry = SearchCache(query_key=query_key, source=source)
                session.add(cache_entry)
            cache_entry.payload_json = json.dumps(payload)
            cache_entry.source = source
            cache_entry.created_at = datetime.now(timezone.utc)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                cache_entry = session.scalar(
                    select(SearchCache).where(SearchCache.query_key == query_key)
                )
                if cache_entry is None:
                    raise
                cache_entry.payload_json = json.dumps(payload)
                cache_entry.source = source
                cache_entry.created_at = datetime.now(timezone.utc)
                session.commit()
    except SQLAlchemyError:
        return


def _ready_session_factory():
    session_factory = get_session_factory()
    if session_factory is None:
        return None
    try:
        create_tables()
    except SQLAlchemyError:
        return None
    return session_factory


def _is_fresh(created_at: datetime) -> bool:
    timestamp = created_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timestamp <= timedelta(hours=CACHE_TTL_HOURS)
