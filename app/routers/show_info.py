from datetime import date
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from app.db.engine import engine

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


def _show_rows(start_date, end_date, prefucture):
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
        filters.append("date(replace(showdate, '/', '-')) >= :start_date")
        params["start_date"] = from_date.isoformat()
    if to_date:
        filters.append("date(replace(showdate, '/', '-')) <= :end_date")
        params["end_date"] = to_date.isoformat()
    if prefucture:
        filters.append("prefucture = :prefucture")
        params["prefucture"] = prefucture
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with engine.connect() as conn:
        return conn.execute(
            text(f"""
                SELECT id, showdate, prefucture, showname, venues, starttime, url
                FROM show_info
                {where_clause}
                ORDER BY date(replace(showdate, '-', '/')), id 
            """),
            params,
        ).fetchall()


def _show_list_context(rows, start_date, end_date, prefucture):
    return {
        "rows": rows,
        "start_date": _display_search_date(start_date),
        "end_date": _display_search_date(end_date),
        "prefucture": prefucture or "",
    }


@router.get("/shows")
def show_list(
    request: Request,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    prefucture: str | None = Query(None),
):
    rows = _show_rows(start_date, end_date, prefucture)

    return templates.TemplateResponse(
        request=request,
        name="show_list.html",
        context=_show_list_context(rows, start_date, end_date, prefucture),
    )


@router.post("/shows/search")
def show_search(
    request: Request,
    start_date: str = Form(""),
    end_date: str = Form(""),
    prefucture: str = Form(""),
):
    try:
        rows = _show_rows(start_date or None, end_date or None, prefucture or None)
    except HTTPException as error:
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
            },
            status_code=200,
        )

    if not rows:
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
            },
            status_code=200,
        )

    return templates.TemplateResponse(
        request=request,
        name="show_list.html",
        context=_show_list_context(rows, start_date, end_date, prefucture),
    )


@router.get("/shows/new")
def show_new(request: Request):
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
):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO show_info
                    (showdate, prefucture, showname, venues, starttime, memo, url)
                VALUES
                    (:showdate, :prefucture, :showname, :venues, :starttime, :memo, :url)
            """),
            {
                "showdate": showdate,
                "prefucture": prefucture or None,
                "showname": showname,
                "venues": venues or None,
                "starttime": starttime or None,
                "memo": memo or None,
                "url": url,
            },
        )

    return RedirectResponse(url="/shows", status_code=303)


@router.get("/shows/{id}")
def show_edit(request: Request, id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, showdate, prefucture, showname, venues, starttime, memo, url
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
        context={"mode": "edit", "row": row, "prefectures": prefectures},
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
):
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
                    url = :url
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
            },
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Show not found")

    return RedirectResponse(url="/shows", status_code=303)


@router.post("/shows/delete/{id}")
def show_delete(id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM show_info WHERE id = :id"),
            {"id": id},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Show not found")

    return RedirectResponse(url="/shows", status_code=303)
