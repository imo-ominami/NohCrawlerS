# Render deployment with PostgreSQL

The web service connects to the Render PostgreSQL database `nohS-db` using `DATABASE_URL`. Set this variable in the Render Dashboard; credentials are not stored in this repository.

## Render configuration

- Build command: `pip install -r requirements.txt`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Database: PostgreSQL `nohS-db`

The SQLite-to-PostgreSQL import has been completed. The app no longer imports from `data.db` or creates SQL snapshot files. `DATABASE_URL` is required; without it, the app stops rather than falling back to SQLite.

For local development, set `DATABASE_URL` to a PostgreSQL connection string before starting the app. Use the Internal URL when the app and database are in the same Render region; otherwise use the External URL with `sslmode=require`.

## Backups

The app does not currently create backups. Use Render PostgreSQL backups or `pg_dump` until the replacement backup process is configured, and periodically verify a restore.
