import os
from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.auth import read_session_token
from app.db.engine import engine
from app.routers import auth, menu, show_info, url_master, user_master, venue_master

app = FastAPI()

APP_ENV = os.getenv("APP_ENV", "development").lower()

if APP_ENV == "production" and not os.getenv("SESSION_SECRET"):
    raise RuntimeError("SESSION_SECRET is required in production")

@app.get("/robots.txt")
async def robots():
    return PlainTextResponse(
        "User-agent: *\nDisallow: /"
    )

@app.middleware("http")
async def require_login(request: Request, call_next):
    if request.url.path in {"/login", "/setup", "/health", "/robots.txt"} or request.url.path.startswith("/static/"):
        return await call_next(request)

    user_id = read_session_token(request.cookies.get("noh_session", ""))
    if user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        user = conn.execute(text("""
            SELECT id, username, role, is_active FROM users WHERE id = :id
        """), {"id": user_id}).mappings().first()
    if not user or not user["is_active"]:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("noh_session", path="/")
        return response
    request.state.current_user = user
    if user["role"] != "admin":
        if request.method in {"GET", "HEAD"} and re.fullmatch(r"/(?:urls|venues|shows)/(?:new|\d+)", request.url.path):
            return PlainTextResponse("管理者権限が必要です。", status_code=403)
    if user["role"] != "admin" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        read_only_posts = {"/shows/search", "/logout"}
        if request.url.path not in read_only_posts:
            return PlainTextResponse("管理者権限が必要です。", status_code=403)
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
app.include_router(user_master.router)
app.include_router(auth.router)
