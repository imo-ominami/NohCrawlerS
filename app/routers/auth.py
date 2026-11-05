from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.auth import create_session_token, hash_password, verify_password
from app.db.engine import engine


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/login")
def login_page(request: Request, error: str | None = None):
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/", status_code=303)
    with engine.connect() as conn:
        has_login_account = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM users WHERE password_hash <> '')"
        )).scalar_one()
    return templates.TemplateResponse(request=request, name="login.html", context={
        "error": error, "initial_setup": not has_login_account,
    })


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT id, password_hash, is_active FROM users WHERE username = :username"),
            {"username": username.strip()},
        ).mappings().first()

    if not user or not user["is_active"] or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "ユーザー名またはパスワードが正しくありません。"},
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        "noh_session",
        create_session_token(user["id"]),
        max_age=60 * 60 * 24 * 14,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("noh_session", path="/")
    return response


@router.get("/setup")
def initial_admin_page(request: Request):
    with engine.connect() as conn:
        has_login_account = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM users WHERE password_hash <> '')"
        )).scalar_one()
    if has_login_account:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="initial_admin.html", context={})


@router.post("/setup")
def initial_admin_create(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if not username or len(password) < 8:
        return templates.TemplateResponse(request=request, name="initial_admin.html", context={
            "error": "ユーザー名を入力し、パスワードは8文字以上にしてください。",
        }, status_code=400)

    with engine.begin() as conn:
        conn.exec_driver_sql("LOCK TABLE users IN EXCLUSIVE MODE")
        has_login_account = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM users WHERE password_hash <> '')"
        )).scalar_one()
        if has_login_account:
            return RedirectResponse(url="/login", status_code=303)
        duplicate = conn.execute(text("SELECT EXISTS(SELECT 1 FROM users WHERE username=:username)"), {
            "username": username,
        }).scalar_one()
        if duplicate:
            return templates.TemplateResponse(request=request, name="initial_admin.html", context={
                "error": "このユーザー名は既存ユーザーが使用しています。別の名前を指定してください。",
            }, status_code=400)
        conn.execute(text("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (:username, :password_hash, 'admin', TRUE)
        """), {"username": username, "password_hash": hash_password(password)})
    return RedirectResponse(url="/login", status_code=303)
