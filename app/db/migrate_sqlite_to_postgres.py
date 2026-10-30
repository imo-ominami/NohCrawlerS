"""Copy application data from data.db into an empty PostgreSQL database.

Run after `alembic upgrade head` with DATABASE_URL pointing at the destination.
"""
import os
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.db.engine import PROJECT_ROOT, resolve_database_url


DATA_TABLES = (
    "users",
    "user_venues",
    "prefucture_mst",
    "common_venues",
    "url_masters",
    "show_info",
    "show_info_old",
    "app_state",
)
SEQUENCED_TABLES = ("common_venues", "show_info", "show_info_old", "url_masters")


def migrate() -> None:
    source_path = Path(os.getenv("SQLITE_SOURCE_PATH", PROJECT_ROOT / "data.db"))
    if not source_path.is_file():
        repository_database = PROJECT_ROOT / "data.db"
        if repository_database.is_file():
            source_path = repository_database
        else:
            print(f"SQLite source database not found; skipping import: {source_path}")
            return

    print(f"Importing SQLite data from: {source_path}")

    target_url = resolve_database_url()
    if target_url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")

    source = create_engine(f"sqlite:///{source_path.resolve().as_posix()}")
    target = create_engine(target_url, pool_pre_ping=True)
    source_inspector = inspect(source)
    target_inspector = inspect(target)
    metadata = MetaData()
    copied = {}

    try:
        with source.connect() as source_connection, target.begin() as target_connection:
            existing_target_data = []
            for name in DATA_TABLES:
                if target_inspector.has_table(name):
                    count = target_connection.execute(
                        text(f'SELECT COUNT(*) FROM "{name}"')
                    ).scalar_one()
                    if count:
                        existing_target_data.append(name)
            if existing_target_data:
                print(
                    "PostgreSQL already contains application data; skipping SQLite import "
                    f"({', '.join(existing_target_data)})"
                )
                return

            for name in DATA_TABLES:
                if not source_inspector.has_table(name) or not target_inspector.has_table(name):
                    continue
                target_table = metadata.tables.get(name)
                if target_table is None:
                    target_table = Table(name, metadata, autoload_with=target_connection)

                source_columns = {
                    column["name"] for column in source_inspector.get_columns(name)
                }
                target_columns = {column.name for column in target_table.columns}
                shared_columns = [
                    column.name for column in target_table.columns
                    if column.name in source_columns and column.name in target_columns
                ]
                source_table = Table(name, MetaData(), autoload_with=source_connection)
                rows = source_connection.execute(
                    select(*(source_table.c[column] for column in shared_columns))
                ).mappings().all()
                if rows:
                    target_connection.execute(target_table.insert(), rows)
                copied[name] = len(rows)

            for name in SEQUENCED_TABLES:
                if not target_inspector.has_table(name):
                    continue
                sequence = target_connection.execute(
                    text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                    {"table_name": f"public.{name}"},
                ).scalar_one_or_none()
                if sequence:
                    max_id = target_connection.execute(
                        text(f'SELECT MAX("id") FROM "{name}"')
                    ).scalar_one_or_none()
                    if max_id is None:
                        target_connection.execute(
                            text("SELECT setval(CAST(:sequence AS regclass), 1, false)"),
                            {"sequence": sequence},
                        )
                    else:
                        target_connection.execute(
                            text("SELECT setval(CAST(:sequence AS regclass), :max_id, true)"),
                            {"sequence": sequence, "max_id": max_id},
                        )
    finally:
        source.dispose()
        target.dispose()

    for name, count in copied.items():
        print(f"{name}: {count} rows copied")


if __name__ == "__main__":
    migrate()
