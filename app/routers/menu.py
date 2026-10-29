from pathlib import Path
from threading import Lock
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.engine import engine
from app.db.sql_snapshots import restore_empty_tables

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
_crawl_lock = Lock()
_used_crawl_tokens = set()


def _menu_context(**context):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """))
        restore_empty_tables(conn, ("prefucture_mst", "app_state"))
        prefectures = conn.execute(text("""
            SELECT prefucture
            FROM prefucture_mst
            ORDER BY code
        """)).fetchall()
        last_crawl = conn.execute(
            text("SELECT value FROM app_state WHERE key = 'last_crawl_at'")
        ).scalar_one_or_none()
    return {"prefectures": prefectures, "last_crawl_at": last_crawl, **context}


@router.get("/")
def menu_page(
    request: Request,
    start_date: str = Query(""),
    end_date: str = Query(""),
    prefucture: str = Query(""),
    favorite_only: bool = Query(False),
    registered: int | None = Query(None),
    new_count: int | None = Query(None),
    error: str | None = Query(None),
    crawl_token: str = Query(""),
):
    crawl_token = crawl_token or uuid4().hex
    result = {"登録公演数": registered} if registered is not None else None
    if result is not None:
        result["registered_count"] = registered
        result["new_count"] = new_count or 0
    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context=_menu_context(
            start_date=start_date,
            end_date=end_date,
            selected_prefucture=prefucture,
            favorite_only=favorite_only,
            result=result,
            error=error,
            crawl_token=crawl_token,
        ),
    )


@router.post("/crawl")
def crawl_site_information(
    crawl_token: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    prefucture: str = Form(""),
    favorite_only: bool = Form(False),
):
    crawl_token = crawl_token or uuid4().hex
    search_params = {
        key: value for key, value in {
            "start_date": start_date,
            "end_date": end_date,
            "prefucture": prefucture,
            "favorite_only": "1" if favorite_only else "",
        }.items() if value
    }
    with _crawl_lock:
        if crawl_token in _used_crawl_tokens:
            return RedirectResponse(
                url=f"/?{urlencode(search_params)}" if search_params else "/",
                status_code=303,
            )
        _used_crawl_tokens.add(crawl_token)

    from app.getnohinfo import run_pipeline

    try:
        result = run_pipeline()
    except (FileNotFoundError, OSError, ValueError, SQLAlchemyError) as error:
        return RedirectResponse(
            url=f"/?{urlencode({'error': str(error), **search_params})}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/?{urlencode({'registered': result['registered_count'], 'new_count': result['new_count'], **search_params})}",
        status_code=303,
    )
