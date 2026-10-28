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

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
_crawl_lock = Lock()
_used_crawl_tokens = set()


def _menu_context(**context):
    with engine.connect() as conn:
        prefectures = conn.execute(text("""
            SELECT prefucture
            FROM prefucture_mst
            ORDER BY code
        """)).fetchall()
    return {"prefectures": prefectures, **context}


@router.get("/")
def menu_page(
    request: Request,
    start_date: str = Query(""),
    end_date: str = Query(""),
    prefucture: str = Query(""),
    registered: int | None = Query(None),
    error: str | None = Query(None),
    crawl_token: str = Query(""),
):
    crawl_token = crawl_token or uuid4().hex
    result = {"登録公演数": registered} if registered is not None else None
    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context=_menu_context(
            start_date=start_date,
            end_date=end_date,
            selected_prefucture=prefucture,
            result=result,
            error=error,
            crawl_token=crawl_token,
        ),
    )


@router.post("/crawl")
def crawl_site_information(crawl_token: str = Form(...)):
    with _crawl_lock:
        if crawl_token in _used_crawl_tokens:
            return RedirectResponse(url="/", status_code=303)
        _used_crawl_tokens.add(crawl_token)

    from app.main_2 import run_pipeline

    try:
        result = run_pipeline()
    except (FileNotFoundError, OSError, ValueError, SQLAlchemyError) as error:
        return RedirectResponse(
            url=f"/?{urlencode({'error': str(error)})}", status_code=303
        )

    return RedirectResponse(
        url=f"/?{urlencode({'registered': result['登録公演数']})}",
        status_code=303,
    )
