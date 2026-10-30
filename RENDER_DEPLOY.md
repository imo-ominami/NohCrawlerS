# Render deployment with PostgreSQL

The web service uses the Render PostgreSQL database resource named `nohS-db`. Render supplies its connection string to the app as `DATABASE_URL`. The attached disk keeps the existing SQLite database available during the one-time data import and stores the app's SQL snapshot files.

## Existing service requirements

The Render workspace must contain a PostgreSQL resource named `nohS-db`. The web service and database must be in the same region so Render can use the private connection string.

Set `APP_USERNAME` and `APP_PASSWORD` in Render. Keep these credentials out of Git.

## Deployment and initial data import

The start command applies Alembic migrations, copies data from `/var/data/data.db` into PostgreSQL, then starts FastAPI. If the attached disk does not yet contain that file, the importer falls back to the repository's `data.db`. The import runs only when a SQLite source exists and the PostgreSQL application tables are empty. Later restarts skip the import once PostgreSQL contains application data.

If PostgreSQL already contains application data, the importer leaves it untouched and logs that it skipped the import. It does not merge two populated databases.

## Local development

Without `DATABASE_URL`, local development continues to use `data.db`. To run locally against PostgreSQL, set `DATABASE_URL` to the PostgreSQL connection string before starting the app. Do not commit credentials.

To run the data import manually after applying migrations:

```powershell
$env:DATABASE_URL = "postgresql://..."
$env:SQLITE_SOURCE_PATH = "C:\path\to\data.db"
alembic upgrade head
python -m app.db.migrate_sqlite_to_postgres
```

The importer adjusts PostgreSQL sequences after copying explicit SQLite IDs.

## Backups

The app writes its table-level SQL snapshots to `/var/data/sql_snapshots`. These snapshots are useful for restoring application tables, but they are not a complete PostgreSQL backup. Use Render PostgreSQL backups or `pg_dump` for full database backups, and periodically verify a restore.
