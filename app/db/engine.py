import os

from sqlalchemy import create_engine, make_url


def resolve_database_url():
    configured_url = os.getenv("DATABASE_URL", "").strip()
    if not configured_url:
        raise RuntimeError("DATABASE_URL is required to connect to PostgreSQL")
    if configured_url.startswith("postgres://"):
        configured_url = "postgresql+psycopg://" + configured_url[len("postgres://"):]
    elif configured_url.startswith("postgresql://"):
        configured_url = "postgresql+psycopg://" + configured_url[len("postgresql://"):]

    database_url = make_url(configured_url)
    if database_url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")
    return database_url


def create_database_engine():
    return create_engine(resolve_database_url(), pool_pre_ping=True)


engine = create_database_engine()
