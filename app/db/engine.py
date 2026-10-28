import os
from pathlib import Path
import shutil

from sqlalchemy import URL, create_engine


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
    return URL.create("sqlite", database=str(resolve_database_path()))


def create_database_engine():
    return create_engine(
        resolve_database_url(),
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


engine = create_database_engine()
