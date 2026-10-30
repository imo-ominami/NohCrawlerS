import base64
import binascii
import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.routers import menu, show_info, url_master, venue_master
from app.db.sql_snapshots import initialize_sql_snapshots

app = FastAPI()


@app.on_event("startup")
def initialize_database_snapshots():
    initialize_sql_snapshots()

APP_ENV = os.getenv("APP_ENV", "development").lower()
APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

if APP_ENV == "production" and (not APP_USERNAME or not APP_PASSWORD):
    raise RuntimeError("APP_USERNAME and APP_PASSWORD are required in production")


@app.middleware("http")
async def require_production_login(request: Request, call_next):
    if APP_ENV != "production" or request.url.path == "/health":
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    authenticated = False
    if separator and scheme.lower() == "basic":
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
            username, colon, password = decoded.partition(":")
            authenticated = (
                bool(colon)
                and hmac.compare_digest(username, APP_USERNAME)
                and hmac.compare_digest(password, APP_PASSWORD)
            )
        except (binascii.Error, UnicodeDecodeError, ValueError):
            authenticated = False

    if not authenticated:
        return PlainTextResponse(
            "Authentication required",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="NohCrawler"'},
        )
    return await call_next(request)


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static"
)

app.include_router(url_master.router)
app.include_router(venue_master.router)
app.include_router(show_info.router)
app.include_router(menu.router)
