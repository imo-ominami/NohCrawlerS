from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.db.engine import engine
from app.input_validation import bounded_text, checkbox_value


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
_ROLES = {"admin", "viewer"}


def _admin_only(request: Request):
    user = getattr(request.state, "current_user", None)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/", status_code=303)
    return None


@router.get("/users")
def user_list(request: Request):
    denied = _admin_only(request)
    if denied:
        return denied
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, username, role, is_active, created_at, updated_at
            FROM users ORDER BY id
        """)).fetchall()
    return templates.TemplateResponse(request=request, name="user_list.html", context={"rows": rows})


@router.get("/users/new")
def user_new(request: Request):
    denied = _admin_only(request)
    if denied:
        return denied
    return templates.TemplateResponse(request=request, name="user_edit.html", context={"mode": "new"})


@router.post("/users/create")
def user_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    is_active: str | None = Form(None),
):
    denied = _admin_only(request)
    if denied:
        return denied
    username = bounded_text(username, "ユーザー名", 255, required=True)
    if not password or len(password) < 8 or len(password) > 1024 or role not in _ROLES:
        return templates.TemplateResponse(request=request, name="user_edit.html", context={
            "mode": "new", "error": "ユーザー名、パスワード（8～1024文字）、権限を確認してください。", "username": username, "role": role,
        }, status_code=400)
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO users (username, password_hash, role, is_active)
                VALUES (:username, :password_hash, :role, :is_active)
            """), {
                "username": username,
                "password_hash": hash_password(password),
                "role": role,
                "is_active": checkbox_value(is_active, "使用可"),
            })
    except IntegrityError:
        return templates.TemplateResponse(request=request, name="user_edit.html", context={
            "mode": "new", "error": "ユーザーを登録できませんでした。ユーザー名が重複していないか確認してください。",
            "username": username, "role": role,
        }, status_code=400)
    return RedirectResponse(url="/users", status_code=303)


@router.get("/users/{user_id}")
def user_edit(request: Request, user_id: int):
    denied = _admin_only(request)
    if denied:
        return denied
    with engine.connect() as conn:
        user = conn.execute(text("""
            SELECT id, username, role, is_active FROM users WHERE id = :id
        """), {"id": user_id}).mappings().first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    return templates.TemplateResponse(request=request, name="user_edit.html", context={"mode": "edit", "user": user})


@router.post("/users/update/{user_id}")
def user_update(
    request: Request,
    user_id: int,
    username: str = Form(...),
    password: str = Form(""),
    role: str = Form(...),
    is_active: str | None = Form(None),
):
    denied = _admin_only(request)
    if denied:
        return denied
    username = bounded_text(username, "ユーザー名", 255, required=True)
    if role not in _ROLES or (password and (len(password) < 8 or len(password) > 1024)):
        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT id, username, role, is_active FROM users WHERE id=:id"),
                {"id": user_id},
            ).mappings().first()
        if not user:
            return RedirectResponse(url="/users", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="user_edit.html",
            context={
                "mode": "edit",
                "user": user,
                "error": "ユーザー名、権限、パスワード（変更する場合は8～1024文字）を確認してください。",
            },
            status_code=400,
        )
    values = {
        "id": user_id,
        "username": username,
        "role": role,
        "is_active": checkbox_value(is_active, "使用可"),
    }
    statement = """
        UPDATE users
        SET username=:username,
            role=:role,
            failed_login_attempts = CASE
                WHEN is_active = FALSE AND :is_active = TRUE THEN 0
                ELSE failed_login_attempts
            END,
            is_active=:is_active,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=:id
    """
    if password:
        statement = statement.replace(
            "updated_at=CURRENT_TIMESTAMP",
            "password_hash=:password_hash, updated_at=CURRENT_TIMESTAMP",
        )
        values["password_hash"] = hash_password(password)
    try:
        with engine.begin() as conn:
            conn.execute(text(statement), values)
    except IntegrityError:
        with engine.connect() as conn:
            user = conn.execute(text("SELECT id, username, role, is_active FROM users WHERE id=:id"), {"id": user_id}).mappings().first()
        return templates.TemplateResponse(request=request, name="user_edit.html", context={
            "mode": "edit", "user": user, "error": "ユーザーを更新できませんでした。ユーザー名が重複していないか確認してください。",
        }, status_code=400)
    return RedirectResponse(url="/users", status_code=303)
