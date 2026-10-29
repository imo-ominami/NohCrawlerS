from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
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
            SELECT
                code,
                prefucture AS prefecture
            FROM prefucture_mst
            ORDER BY code
        """)
    ).fetchall()


@router.get("/venues")
def venue_list(request: Request):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    c.id,
                    c.code,
                    p.prefucture AS prefecture,
                    c.venue
                FROM common_venues c
                JOIN prefucture_mst p
                    ON p.code = c.code
                ORDER BY c.code, c.id
            """)
        ).fetchall()

    return templates.TemplateResponse(
        request=request,
        name="venue_list.html",
        context={"rows": rows},
    )


@router.get("/venues/new")
def venue_new(request: Request):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.connect() as conn:
        prefectures = _get_prefectures(conn)

    return templates.TemplateResponse(
        request=request,
        name="venue_edit.html",
        context={"mode": "new", "prefectures": prefectures},
    )


@router.post("/venues/create")
def venue_create(
    code: int = Form(...),
    venue: str = Form(...),
):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.begin() as conn:
        if conn.execute(
            text("SELECT 1 FROM prefucture_mst WHERE code = :code"),
            {"code": code},
        ).first() is None:
            raise HTTPException(status_code=422, detail="Invalid prefecture code")

        conn.execute(
            text("""
                INSERT INTO common_venues (code, venue)
                VALUES (:code, :venue)
            """),
            {"code": code, "venue": venue},
        )

    write_table_snapshot("common_venues")
    return RedirectResponse(url="/venues", status_code=303)


@router.get("/venues/{id}")
def venue_edit(request: Request, id: int):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, code, venue
                FROM common_venues
                WHERE id = :id
            """),
            {"id": id},
        ).fetchone()
        prefectures = _get_prefectures(conn)

    if row is None:
        raise HTTPException(status_code=404, detail="Venue not found")

    return templates.TemplateResponse(
        request=request,
        name="venue_edit.html",
        context={
            "mode": "edit",
            "row": row,
            "prefectures": prefectures,
        },
    )


@router.post("/venues/update/{id}")
def venue_update(
    id: int,
    code: int = Form(...),
    venue: str = Form(...),
):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.begin() as conn:
        if conn.execute(
            text("SELECT 1 FROM prefucture_mst WHERE code = :code"),
            {"code": code},
        ).first() is None:
            raise HTTPException(status_code=422, detail="Invalid prefecture code")

        result = conn.execute(
            text("""
                UPDATE common_venues
                SET code = :code, venue = :venue
                WHERE id = :id
            """),
            {"id": id, "code": code, "venue": venue},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Venue not found")

    write_table_snapshot("common_venues")
    return RedirectResponse(url="/venues", status_code=303)


@router.post("/venues/delete/{id}")
def venue_delete(id: int):
    ensure_restored("prefucture_mst", "common_venues")
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM common_venues WHERE id = :id"),
            {"id": id},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Venue not found")

    write_table_snapshot("common_venues")
    return RedirectResponse(url="/venues", status_code=303)
