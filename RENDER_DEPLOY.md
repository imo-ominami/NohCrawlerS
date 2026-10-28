# Render deployment with SQLite

Render runs one shared FastAPI app and stores its SQLite database on an attached persistent disk. Users access the app in a browser; their devices do not need Python or a virtual environment.

## Before deploying

1. Create a **private** Git repository from this `Smartphone` folder. The current `data.db` is intentionally included so the first Render startup can seed the persistent disk with the existing data. Keep this repository private.
2. Connect the repository to Render and create a Blueprint using `render.yaml`.
3. When prompted, choose an `APP_USERNAME` and a strong `APP_PASSWORD`. Keep these values out of Git.
4. Wait for the first deploy. On first startup, the app copies `data.db` to `/var/data/data.db`, then Alembic applies any pending migrations. Later deploys use the copy on the persistent disk and preserve its contents.
5. Open the service's `onrender.com` URL and sign in with the shared credentials.

## Render configuration

- Build: `pip install -r requirements.txt`
- Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- SQLite file: `/var/data/data.db` on the attached persistent disk

The Blueprint uses Render's smallest paid web plan and a 1 GB disk. At current listed rates, that is about **$7.25/month** before taxes or other usage: $7/month for compute plus $0.25/GB/month for disk. Check [Render pricing](https://render.com/pricing) before deploying.

The disk belongs to one service instance; this deployment is configured for a single instance. SQLite allows many readers but serializes writes, so this is appropriate for a small group with light editing. Keep periodic copies of `data.db` as backups. Render disks persist across deploys and restarts, but do not replace backups.

Production uses HTTP Basic authentication with one shared account. Render provides HTTPS for web services. Share the credentials only with intended users.
