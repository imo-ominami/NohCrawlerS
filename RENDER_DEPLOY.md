# Render deployment with PostgreSQL

The web service connects to the Render PostgreSQL database `nohS-db` using `DATABASE_URL`. Set this variable in the Render Dashboard; it is intentionally not stored in this repository. The attached disk keeps the existing SQLite database available during the one-time data import and stores the app's SQL snapshot files.

## Existing service requirements

The Render workspace must contain the PostgreSQL database `nohS-db`. Use its Internal Database URL if the web service and database are in the same region. Otherwise use its External Database URL with `sslmode=require`.

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
