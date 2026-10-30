from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from app.db.engine import engine
from app.db.sql_snapshots import ensure_restored, write_table_snapshot

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def _get_prefectures(conn):
    return conn.execute(
        text("""
            SELECT prefucture
            FROM prefucture_mst
            ORDER BY code
        """)
    ).fetchall()


def _display_search_date(value):
    return value.replace("-", "/") if value else ""


def _show_rows(start_date, end_date, prefucture, favorite_only=False):
    ensure_restored("show_info")
    try:
        from_date = date.fromisoformat(start_date.replace("/", "-")) if start_date else None
        to_date = date.fromisoformat(end_date.replace("/", "-")) if end_date else None
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="検索条件の日付が正しくありません。YYYY/MM/DD形式で入力してください。",
        ) from error

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="開始日は終了日以前の日付を指定してください。",
        )

    if prefucture:
        ensure_restored("prefucture_mst")
        with engine.connect() as conn:
            valid_prefectures = {row.prefucture for row in _get_prefectures(conn)}
        if prefucture not in valid_prefectures:
            raise HTTPException(
                status_code=422,
                detail="都道府県の指定が正しくありません。",
            )

    filters = []
    params = {}
    if from_date:
        filters.append("replace(showdate, '/', '-') >= :start_date")
        params["start_date"] = from_date.isoformat()
    if to_date:
        filters.append("replace(showdate, '/', '-') <= :end_date")
        params["end_date"] = to_date.isoformat()
    if prefucture:
        filters.append("prefucture = :prefucture")
        params["prefucture"] = prefucture
    if favorite_only:
        filters.append("favorite = 1")
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with engine.connect() as conn:
        return conn.execute(
            text(f"""
                SELECT id, showdate, prefucture, showname, venues, starttime, url, favorite, new
                FROM show_info
                {where_clause}
                ORDER BY replace(showdate, '/', '-'), id
            """),
            params,
        ).fetchall()


def _show_list_context(rows, start_date, end_date, prefucture, favorite_only=False):
    return {
        "rows": rows,
        "start_date": _display_search_date(start_date),
        "end_date": _display_search_date(end_date),
        "prefucture": prefucture or "",
        "favorite_only": favorite_only,
    }


def _show_list_url(start_date, end_date, prefucture, favorite_only=False):
    params = {
        key: value
        for key, value in {
            "start_date": start_date,
            "end_date": end_date,
            "prefucture": prefucture,
            "favorite_only": "1" if favorite_only else "",
        }.items()
        if value
    }
    return f"/shows?{urlencode(params)}" if params else "/shows"


@router.get("/shows")
def show_list(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    prefucture: str | None = Query(None),
    favorite_only: bool = Query(False),
):
    rows = _show_rows(start_date, end_date, prefucture, favorite_only)

    return templates.TemplateResponse(
        request=request,
        name="show_list.html",
        context=_show_list_context(rows, start_date, end_date, prefucture, favorite_only),
    )


@router.post("/shows/favorites")
async def save_show_favorites(request: Request):
    try:
        favorites = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid favorite data") from error

    if not isinstance(favorites, list):
        raise HTTPException(status_code=400, detail="Invalid favorite data")

    ensure_restored("show_info")
    with engine.begin() as conn:
        for item in favorites:
            if not isinstance(item, dict):
                continue
            try:
                show_id = int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
            conn.execute(
                text("UPDATE show_info SET favorite = :favorite WHERE id = :id"),
                {"id": show_id, "favorite": int(bool(item.get("favorite")))},
            )

    write_table_snapshot("show_info")
    return {"saved": len(favorites)}


@router.post("/shows/search")
def show_search(
    request: Request,
    start_date: str = Form(""),
    end_date: str = Form(""),
    prefucture: str = Form(""),
    favorite_only: bool = Form(False),
):
    try:
        rows = _show_rows(start_date or None, end_date or None, prefucture or None, favorite_only)
    except HTTPException as error:
        ensure_restored("prefucture_mst")
        with engine.connect() as conn:
            prefectures = _get_prefectures(conn)
        return templates.TemplateResponse(
            request=request,
            name="menu.html",
            context={
                "prefectures": prefectures,
                "search_error": error.detail,
                "start_date": _display_search_date(start_date),
                "end_date": _display_search_date(end_date),
                "selected_prefucture": prefucture,
                "favorite_only": favorite_only,
            },
            status_code=200,
        )

    if not rows:
        ensure_restored("prefucture_mst")
        with engine.connect() as conn:
            prefectures = _get_prefectures(conn)
        return templates.TemplateResponse(
            request=request,
            name="menu.html",
            context={
                "prefectures": prefectures,
                "search_error": "条件に合う公演情報がありません。",
                "start_date": _display_search_date(start_date),
                "end_date": _display_search_date(end_date),
                "selected_prefucture": prefucture,
                "favorite_only": favorite_only,
            },
            status_code=200,
        )

    return templates.TemplateResponse(
        request=request,
        name="show_list.html",
        context=_show_list_context(rows, start_date, end_date, prefucture, favorite_only),
    )


@router.get("/shows/new")
def show_new(request: Request):
    ensure_restored("prefucture_mst")
    with engine.connect() as conn:
        prefectures = _get_prefectures(conn)

    return templates.TemplateResponse(
        request=request,
        name="show_edit.html",
        context={"mode": "new", "prefectures": prefectures},
    )


@router.post("/shows/create")
def show_create(
    showdate: str = Form(...),
    showname: str = Form(...),
    url: str = Form(...),
    prefucture: str | None = Form(None),
    venues: str | None = Form(None),
    starttime: str | None = Form(None),
    memo: str | None = Form(None),
    favorite: bool = Form(False),
):
    ensure_restored("show_info")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO show_info
                    (showdate, prefucture, showname, venues, starttime, memo, url, favorite)
                VALUES
                    (:showdate, :prefucture, :showname, :venues, :starttime, :memo, :url, :favorite)
            """),
            {
                "showdate": showdate,
                "prefucture": prefucture or None,
                "showname": showname,
                "venues": venues or None,
                "starttime": starttime or None,
                "memo": memo or None,
                "url": url,
                "favorite": int(favorite),
            },
        )

    write_table_snapshot("show_info")
    return RedirectResponse(url="/shows", status_code=303)


@router.get("/shows/{id}")
def show_edit(
    request: Request,
    id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    prefucture: str | None = Query(None),
    favorite_only: bool = Query(False),
):
    ensure_restored("show_info")
    ensure_restored("prefucture_mst")
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, showdate, prefucture, showname, venues, starttime, memo, url, favorite
                FROM show_info
                WHERE id = :id
            """),
            {"id": id},
        ).fetchone()
        prefectures = _get_prefectures(conn)

    if row is None:
        raise HTTPException(status_code=404, detail="Show not found")

    return templates.TemplateResponse(
        request=request,
        name="show_edit.html",
        context={
            "mode": "edit",
            "row": row,
            "prefectures": prefectures,
            **_show_list_context([], start_date, end_date, prefucture, favorite_only),
        },
    )


@router.post("/shows/update/{id}")
def show_update(
    id: int,
    showdate: str = Form(...),
    showname: str = Form(...),
    url: str = Form(...),
    prefucture: str | None = Form(None),
    venues: str | None = Form(None),
    starttime: str | None = Form(None),
    memo: str | None = Form(None),
    favorite: bool = Form(False),
    filter_start_date: str = Form(""),
    filter_end_date: str = Form(""),
    filter_prefucture: str = Form(""),
    filter_favorite_only: bool = Form(False),
):
    ensure_restored("show_info")
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE show_info
                SET showdate = :showdate,
                    prefucture = :prefucture,
                    showname = :showname,
                    venues = :venues,
                    starttime = :starttime,
                    memo = :memo,
                    url = :url,
                    favorite = :favorite
                WHERE id = :id
            """),
            {
                "id": id,
                "showdate": showdate,
                "prefucture": prefucture or None,
                "showname": showname,
                "venues": venues or None,
                "starttime": starttime or None,
                "memo": memo or None,
                "url": url,
                "favorite": int(favorite),
            },
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Show not found")

    write_table_snapshot("show_info")
    return RedirectResponse(
        url=_show_list_url(
            filter_start_date, filter_end_date, filter_prefucture, filter_favorite_only
        ),
        status_code=303,
    )


@router.post("/shows/delete/{id}")
def show_delete(
    id: int,
    filter_start_date: str = Form(""),
    filter_end_date: str = Form(""),
    filter_prefucture: str = Form(""),
    filter_favorite_only: bool = Form(False),
):
    ensure_restored("show_info")
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM show_info WHERE id = :id"),
            {"id": id},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Show not found")

    write_table_snapshot("show_info")
    return RedirectResponse(
        url=_show_list_url(
            filter_start_date, filter_end_date, filter_prefucture, filter_favorite_only
        ),
        status_code=303,
    )
