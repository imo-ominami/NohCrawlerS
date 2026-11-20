# Render deployment with PostgreSQL

The web service connects to the Render PostgreSQL database `nohS-db` using `DATABASE_URL`. Set this variable in the Render Dashboard; credentials are not stored in this repository. Set `SESSION_SECRET` to a long, random secret for signed login cookies.

## Render configuration

- Build command: `pip install -r requirements.txt`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Database: PostgreSQL `nohS-db`

The SQLite-to-PostgreSQL import has been completed. The app no longer imports from `data.db` or creates SQL snapshot files. `DATABASE_URL` is required; without it, the app stops rather than falling back to SQLite. Run `alembic upgrade head` before using the application. On a database with no usable password hashes, visit `/setup` once to create the initial administrator account.

For local development, set `DATABASE_URL` to a PostgreSQL connection string before starting the app. Use the Internal URL when the app and database are in the same Render region; otherwise use the External URL with `sslmode=require`.

## Backups and recovery

The GitHub Actions workflow at `.github/workflows/postgres-backup.yml` is currently disabled (`backup` job condition is `false`), so it does not create or upload backups. To resume backups, change that condition to `true`. When enabled, it creates a daily custom-format `pg_dump` backup and uploads it to Cloudflare R2 at 18:00 UTC (03:00 Japan time), and can also be started manually from the repository's **Actions** tab. GitHub-hosted runners and GitHub Actions secrets are used; no backup is stored on the Render service or in the repository.

### One-time setup

1. Create a private bucket in Cloudflare R2. Create an R2 API token with read/write object access limited to this bucket. Do not enable public access.
2. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `RENDER_DATABASE_URL`: the Render PostgreSQL **External Database URL**. Treat this URL as a password.
   - `R2_ACCOUNT_ID`: the Cloudflare account ID.
   - `R2_BUCKET`: the bucket name.
   - `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`: the credentials for the bucket-scoped R2 API token.
3. Run **Actions → PostgreSQL backup to Cloudflare R2 → Run workflow** once and confirm it succeeds. Scheduled workflows run from the default branch and GitHub may delay scheduled starts.

The Render database must accept external connections from the GitHub-hosted runner. GitHub-hosted runners do not have a stable outbound IP by default; if the database is restricted to specific source IPs, use a runner with a stable IP rather than broadly weakening the database's access controls.

The workflow installs `pg_dump` from the PostgreSQL project's APT repository and `aws` on an Ubuntu GitHub-hosted runner. A successful run verifies that the dump can be listed and that the uploaded R2 object's size matches the local dump. GitHub Actions will report a failed run if configuration, backup, or upload fails. Configure GitHub notifications so failures are noticed.

Backups are stored under `postgres/` in R2 and are not automatically deleted. Configure an R2 lifecycle rule if you want a retention limit, keeping in mind that expired backups cannot be used for recovery. Storage charges may apply.

### Deletion detection and recovery

The `postgres-monitor.yml` workflow checks the original Render PostgreSQL resource once per day at 18:17 UTC (03:17 Japan time). If Render API confirms the resource is missing (HTTP 404/410), the workflow fails visibly; configure GitHub Actions failure notifications for the repository so the alert is delivered. A timeout, authentication failure, or other API error also fails the check, but is explicitly not treated as confirmation of deletion. The monitor cannot restore data by itself because the chosen recovery mode does not automatically create a replacement database.

To recover after the alert:

1. Manually create a new Render PostgreSQL database in the region used by the web service. Keep it empty; restoring is refused if user tables already exist. The replacement database's availability, plan, and any charges are controlled by Render.
2. Add or update these GitHub Actions repository secrets:
   - `RECOVERY_DATABASE_URL`: the replacement database's **External Database URL**, used by the GitHub-hosted runner to restore the backup.
   - `RECOVERY_RENDER_DATABASE_URL`: the replacement database's **Internal Database URL**, used by the Render web service. Use the external URL only if an internal URL is unavailable and the connection is otherwise permitted.
3. In **Actions → Recover PostgreSQL from Cloudflare R2 → Run workflow**, start the recovery. The workflow confirms the original database is deleted, checks that the external and internal URLs identify the same database, selects the newest timestamped backup in R2, validates and restores it, verifies that user tables exist, updates the web service's `DATABASE_URL` through the Render API, and triggers a deploy. It refuses to overwrite a non-empty replacement database.
4. Confirm the deploy is live and verify the site and restored data in the Render Dashboard. Update the `RENDER_DATABASE_URL` GitHub secret used by the daily backup workflow to the new database's External Database URL; otherwise subsequent daily backups will continue attempting to use the deleted database.

The recovery workflow also requires these GitHub Actions secrets:

- `RENDER_API_KEY`: a Render API key with permission to inspect the old PostgreSQL resource, update the web service's `DATABASE_URL`, and trigger its deploy. Treat it as a credential with access to your Render account.
- `RENDER_POSTGRES_ID`: the original PostgreSQL resource ID. Keep this value so the monitor and recovery workflow can confirm deletion.
- `RENDER_SERVICE_ID`: the Render web service ID.
- `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`: the account, private bucket, and R2 API credentials described above. The recovery workflow needs read access to the bucket; the backup workflow needs write access.

`DATABASE_URL` must be configured directly on the Render web service, not inherited from a linked environment group, for the recovery workflow to update it. The original resource ID remains configured after recovery, so monitoring will continue to report it as deleted; update `RENDER_POSTGRES_ID` to the new database ID after recovery. The backup workflow's `RENDER_DATABASE_URL` must also be updated as described above.

Recovery uses the most recent completed backup, so changes since that backup was created may be lost. The workflow and a successful deploy do not substitute for periodically testing a restore and verifying application data.

If a restore fails partway through, create another empty replacement database before retrying; the partial restore leaves objects behind and the workflow intentionally refuses to overwrite them.

For a manual restore outside GitHub Actions, download the selected backup and restore it into a **new, empty PostgreSQL database**. For example, with AWS CLI installed:

```powershell
aws s3 cp s3://YOUR_BUCKET/postgres/BACKUP_FILENAME.dump .\noh-crawler-backup.dump `
  --endpoint-url https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
pg_restore --no-owner --no-acl --dbname="$env:NEW_DATABASE_URL" .\noh-crawler-backup.dump
```

In PowerShell, set the destination connection string in `$env:NEW_DATABASE_URL` before running the restore command. Provide the R2 credentials to AWS CLI through environment variables or its credential profile; do not put credentials in the command or commit them. After restoring, update the Render service's `DATABASE_URL` to the new database and verify the application and its data before deleting or changing any remaining database.

Periodically restore a backup into a separate test database. A successful upload alone does not prove that the database can be fully recovered.
