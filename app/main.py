import os
import hmac
from pathlib import Path
import re
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.auth import create_csrf_token, read_session_token, verify_csrf_token
from app.db.engine import engine
from app.routers import auth, menu, show_info, url_master, user_master, venue_master

app = FastAPI()

APP_ENV = os.getenv("APP_ENV", "development").lower()
_CSRF_COOKIE = "noh_csrf"
_CSRF_MAX_AGE = 60 * 60 * 24 * 14
_MAX_REQUEST_BYTES = 1_048_576

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


@app.middleware("http")
async def protect_forms(request: Request, call_next):
    if request.url.path.startswith("/static/"):
        return await call_next(request)

    csrf_cookie = request.cookies.get(_CSRF_COOKIE, "")
    request.state.csrf_token = csrf_cookie if verify_csrf_token(csrf_cookie) else ""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        if not verify_csrf_token(csrf_cookie):
            csrf_cookie = create_csrf_token()
        request.state.csrf_token = csrf_cookie
        response = await call_next(request)
        if not request.cookies.get(_CSRF_COOKIE) or not verify_csrf_token(request.cookies.get(_CSRF_COOKIE, "")):
            response.set_cookie(
                _CSRF_COOKIE,
                csrf_cookie,
                max_age=_CSRF_MAX_AGE,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
                path="/",
            )
        return response

    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return await call_next(request)
    if not verify_csrf_token(csrf_cookie):
        return PlainTextResponse("CSRF token is missing or invalid.", status_code=403)

    content_type = request.headers.get("content-type", "").lower().split(";", 1)[0].strip()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_REQUEST_BYTES:
                return PlainTextResponse("Request body is too large.", status_code=413)
        except ValueError:
            return PlainTextResponse("Invalid Content-Length.", status_code=400)
    body = await request.body()
    if len(body) > _MAX_REQUEST_BYTES:
        return PlainTextResponse("Request body is too large.", status_code=413)
    if content_type == "application/json":
        submitted_token = request.headers.get("x-csrf-token", "")
    elif content_type == "application/x-www-form-urlencoded":
        try:
            form = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=1000)
        except (UnicodeDecodeError, ValueError):
            return PlainTextResponse("Invalid form data.", status_code=400)
        csrf_values = form.get("_csrf_token", [])
        if len(csrf_values) != 1:
            return PlainTextResponse("CSRF token is missing or invalid.", status_code=403)
        submitted_token = csrf_values[0]
    else:
        return PlainTextResponse("Unsupported request content type.", status_code=415)
    if not hmac.compare_digest(csrf_cookie, submitted_token):
        return PlainTextResponse("CSRF token is missing or invalid.", status_code=403)
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
