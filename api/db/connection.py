import os
from typing import Any
from urllib.parse import quote_plus

import psycopg2


def _clean_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def get_db_connect_kwargs() -> dict[str, Any]:
    return {
        "dbname": _clean_env("DB_NAME"),
        "user": _clean_env("DB_USER"),
        "password": _clean_env("DB_PASSWORD"),
        "host": _clean_env("DB_HOST"),
        "port": _clean_env("DB_PORT"),
    }


def get_database_url() -> str | None:
    database_url = _clean_env("DATABASE_URL")
    if database_url:
        return database_url

    kwargs = get_db_connect_kwargs()
    if not kwargs.get("dbname"):
        return None

    user = quote_plus(kwargs.get("user") or "")
    password = quote_plus(kwargs.get("password") or "")
    auth = user
    if password:
        auth = f"{auth}:{password}"
    host = kwargs.get("host") or "localhost"
    port = kwargs.get("port") or "5432"
    if auth:
        auth = f"{auth}@"
    return f"postgresql://{auth}{host}:{port}/{kwargs['dbname']}"


def connect_db(*, cursor_factory=None):
    database_url = get_database_url()
    if database_url:
        kwargs: dict[str, Any] = {}
        if cursor_factory is not None:
            kwargs["cursor_factory"] = cursor_factory
        return psycopg2.connect(database_url, **kwargs)

    kwargs = {key: value for key, value in get_db_connect_kwargs().items() if value is not None}
    if cursor_factory is not None:
        kwargs["cursor_factory"] = cursor_factory
    return psycopg2.connect(**kwargs)
