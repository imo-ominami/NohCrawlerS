from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi import Form
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from app.db.engine import engine

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

@router.get("/urls")
def url_list(request: Request):
    with engine.connect() as conn:

        result = conn.execute(
            text("""
                SELECT
                    id,
                    name,
                    url,
                    enabled
                FROM url_masters
                ORDER BY enabled DESC, id
            """)
        )

        rows = result.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="url_list.html",
        context={
            "rows": rows
        }
    )

@router.get("/urls/new")
def url_new(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="url_edit.html",
        context={
            "mode": "new"
        }
    )

@router.post("/urls/create")
def url_create(
    name: str = Form(...),
    url: str = Form(...),
    enabled: str | None = Form(None)
):

    enabled_value = bool(enabled)
    with engine.begin() as conn:

        conn.execute(
            text("""
                INSERT INTO url_masters
                (
                    name,
                    url,
                    enabled
                )
                VALUES
                (
                    :name,
                    :url,
                    :enabled
                )
            """),
            {
                "name": name,
                "url": url,
                "enabled": enabled_value
            }
        )

    return RedirectResponse(
        url="/urls",
        status_code=303
    )

@router.get("/urls/{id}")
def url_edit(
    request: Request,
    id: int
):
    with engine.connect() as conn:

        row = conn.execute(
            text("""
                SELECT
                    id,
                    name,
                    url,
                    enabled
                FROM url_masters
                WHERE id = :id
            """),
            {"id": id}
        ).fetchone()

    return templates.TemplateResponse(
        request=request,
        name="url_edit.html",
        context={
            "mode": "edit",
            "row": row
        }
    )

@router.post("/urls/update/{id}")
def url_update(
    id: int,
    name: str = Form(...),
    url: str = Form(...),
    enabled: str | None = Form(None)
):

    enabled_value = bool(enabled)
    with engine.begin() as conn:

        conn.execute(
            text("""
                UPDATE url_masters
                SET
                    name = :name,
                    url = :url,
                    enabled = :enabled
                WHERE id = :id
            """),
            {
                "id": id,
                "name": name,
                "url": url,
                "enabled": enabled_value
            }
        )

    return RedirectResponse(
        url="/urls",
        status_code=303
    )

@router.post("/urls/delete/{id}")
def url_delete(id: int):
    with engine.begin() as conn:

        conn.execute(
            text("""
                DELETE
                FROM url_masters
                WHERE id = :id
            """),
            {"id": id}
        )

    return RedirectResponse(
        url="/urls",
        status_code=303
    )
