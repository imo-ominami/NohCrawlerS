import os
from pathlib import Path
import shutil

from sqlalchemy import URL, create_engine, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_database_path():
    database_path = Path(os.getenv("SQLITE_DB_PATH", PROJECT_ROOT / "data.db"))
    initial_database = PROJECT_ROOT / "data.db"

    if (
        not database_path.exists()
        and initial_database.is_file()
        and database_path.resolve() != initial_database.resolve()
    ):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(initial_database, database_path)

    return database_path


def resolve_database_url():
    configured_url = os.getenv("DATABASE_URL", "").strip()
    if configured_url:
        if configured_url.startswith("postgres://"):
            configured_url = "postgresql+psycopg://" + configured_url[len("postgres://"):]
        elif configured_url.startswith("postgresql://"):
            configured_url = "postgresql+psycopg://" + configured_url[len("postgresql://"):]
        return make_url(configured_url)

    # Keep SQLite available for local development and the one-time data export.
    return URL.create("sqlite", database=str(resolve_database_path()))


def create_database_engine():
    database_url = resolve_database_url()
    engine_options = {"pool_pre_ping": True}
    if database_url.get_backend_name() == "sqlite":
        engine_options["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **engine_options)


engine = create_database_engine()
