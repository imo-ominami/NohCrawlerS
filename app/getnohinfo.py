from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import pandas as pd
import requests
from sqlalchemy import text

from .crawler import get_data
from .db.engine import engine as database_engine
from .output import EVENT_COLUMNS, _merge_events

def load_sites():
    """有効なURLマスタから巡回先を読み込む。"""
    with database_engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT name, url
            FROM url_masters
            WHERE enabled = TRUE
            ORDER BY id
        """)).fetchall()

    configured_sites = []
    for row in rows:
        name = str(row.name or "").strip()
        url = str(row.url or "").strip()
        if not name and not url:
            continue
        if not name or not url:
            raise ValueError("サイト情報には「サイト名」と「URL」の両方を入力してください")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"サイト「{name}」のURLはhttpまたはhttpsで指定してください: {url}")
        configured_sites.append((name, url))
    return configured_sites


def run_pipeline():
    sites = load_sites()
    if not sites:
        raise ValueError("有効なURLマスタがありません")

    with database_engine.begin() as conn:
        conn.execute(text("DELETE FROM show_info_old"))
        conn.execute(text("""
            INSERT INTO show_info_old
                (showdate, prefucture, showname, venues, starttime, memo, url, favorite, new)
            SELECT showdate, prefucture, showname, venues, starttime, memo, url, favorite, new
            FROM show_info
        """))
    events = []
    seen_urls = set()
    successful_sites = 0
    for site_name, url in sites:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        print(f"[情報取得] {site_name} ({url})")
        try:
            site_events = get_data(url)
        except requests.RequestException as error:
            print(f"  取得失敗: {error}")
            continue
        successful_sites += 1
        for event in site_events:
            event["サイト名"] = site_name
        print(f"  公演情報: {len(site_events)}件")
        events.extend(site_events)

    if successful_sites == 0:
        raise ValueError("巡回先から能情報を取得できませんでした。既存の公演情報は変更していません")

    with database_engine.begin() as conn:
        conn.execute(text("DELETE FROM show_info"))
        if events:
            conn.execute(
                text("""
                    INSERT INTO show_info
                        (showdate, prefucture, showname, venues, starttime, memo, url, favorite, new)
                    VALUES
                        (:showdate, :prefucture, :showname, :venues, :starttime, :memo, :url, 0, 0)
                """),
                [
                    {
                        "showdate": event["公演日"],
                        "prefucture": event["都道府県"] or None,
                        "showname": event["公演名"],
                        "venues": event["会場"] or None,
                        "starttime": event["開演時間"] or None,
                        "memo": event["備考"] or None,
                        "url": event["掲載URL"],
                    }
                    for event in events
                ],
            )

        registered_rows = conn.execute(text("""
            SELECT showdate, prefucture, showname, venues, starttime, memo, url
            FROM show_info
            ORDER BY id
        """)).fetchall()
        registered_events = pd.DataFrame(
            [
                {
                    "公演日": row.showdate,
                    "都道府県": row.prefucture or "",
                    "公演名": row.showname,
                    "会場": row.venues or "",
                    "開演時間": row.starttime or "",
                    "備考": row.memo or "",
                    "掲載URL": row.url,
                }
                for row in registered_rows
            ],
            columns=EVENT_COLUMNS,
        )
        merged_events = _merge_events(registered_events, conn=conn)

        conn.execute(text("DELETE FROM show_info"))
        merged_rows = [
            {
                "showdate": str(event["公演日"]),
                "prefucture": event["都道府県"] or None,
                "showname": event["公演名"],
                "venues": event["会場"] or None,
                "starttime": event["開演時間"] or None,
                "memo": event["備考"] or None,
                "url": event["掲載URL"],
            }
            for event in merged_events.to_dict("records")
        ]
        if merged_rows:
            old_shows = conn.execute(text(
                "SELECT showdate, showname, venues, starttime, favorite FROM show_info_old"
            )).fetchall()
            show_key = lambda show: (
                show.showdate,
                show.showname,
                show.venues,
                show.starttime,
            )
            old_favorites = {show_key(row): int(row.favorite or 0) for row in old_shows}
            for row in merged_rows:
                key = (row["showdate"], row["showname"], row["venues"], row["starttime"])
                row["favorite"] = old_favorites.get(key, 0)
                row["new"] = 0 if key in old_favorites else 1
            conn.execute(
                text("""
                    INSERT INTO show_info
                        (showdate, prefucture, showname, venues, starttime, memo, url, favorite, new)
                    VALUES
                        (:showdate, :prefucture, :showname, :venues, :starttime, :memo, :url, :favorite, :new)
                """),
                merged_rows,
            )

        conn.execute(text("""
            INSERT INTO app_state (key, value) VALUES ('last_crawl_at', :value)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """), {"value": datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d %H:%M:%S")})

    result = {
        "取得公演数": len(events),
        "統合後公演数": len(merged_rows),
        "登録公演数": len(merged_rows),
        "new_count": sum(row["new"] == 1 for row in merged_rows),
        "registered_count": len(merged_rows),
    }
    print(f"[公演一覧] {result['登録公演数']}件を登録")
    return result


if __name__ == "__main__":
    run_pipeline()
