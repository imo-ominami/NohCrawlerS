from pathlib import Path
import re
from threading import Lock
from time import monotonic
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.engine import engine
from app.input_validation import bounded_text, checkbox_value

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
_crawl_lock = Lock()
_CRAWL_TOKEN_TTL_SECONDS = 10 * 60
_used_crawl_tokens = {}


def _menu_context(**context):
    with engine.begin() as conn:
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
    start_date = bounded_text(start_date, "開始日", 10)
    end_date = bounded_text(end_date, "終了日", 10)
    prefucture = bounded_text(prefucture, "都道府県", 100)
    error = bounded_text(error or "", "エラー", 500)
    if not re.fullmatch(r"[0-9a-f]{32}", crawl_token):
        crawl_token = uuid4().hex
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
    favorite_only: str | None = Form(None),
):
    crawl_token = bounded_text(crawl_token, "取得トークン", 32)
    if crawl_token and not re.fullmatch(r"[0-9a-f]{32}", crawl_token):
        raise HTTPException(status_code=422, detail="取得トークンの形式が正しくありません。")
    crawl_token = crawl_token or uuid4().hex
    start_date = bounded_text(start_date, "開始日", 10)
    end_date = bounded_text(end_date, "終了日", 10)
    prefucture = bounded_text(prefucture, "都道府県", 100)
    favorite_value = checkbox_value(favorite_only, "お気に入り")
    search_params = {
        key: value for key, value in {
            "start_date": start_date,
            "end_date": end_date,
            "prefucture": prefucture,
            "favorite_only": "1" if favorite_value else "",
        }.items() if value
    }
    with _crawl_lock:
        now = monotonic()
        expired_tokens = [
            token for token, expires_at in _used_crawl_tokens.items()
            if expires_at <= now
        ]
        for token in expired_tokens:
            del _used_crawl_tokens[token]

        if crawl_token in _used_crawl_tokens:
            return RedirectResponse(
                url=f"/?{urlencode(search_params)}" if search_params else "/",
                status_code=303,
            )
        _used_crawl_tokens[crawl_token] = now + _CRAWL_TOKEN_TTL_SECONDS

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
