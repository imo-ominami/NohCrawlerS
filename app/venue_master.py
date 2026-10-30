import re
import unicodedata

from sqlalchemy import text

from .db.engine import engine


def _normalize(value):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", str(value or "")).casefold())


def _load_venue_master(conn):
    master = {}
    rows = conn.execute(text("""
        SELECT c.venue, p.prefucture
        FROM common_venues AS c
        JOIN prefucture_mst AS p ON p.code = c.code
        ORDER BY c.id
    """))
    for row in rows:
        venue = str(row.venue or "").strip()
        prefecture = str(row.prefucture or "").strip()
        if prefecture and venue:
            master[_normalize(venue)] = (venue, prefecture)
    return master


def _venue_master(conn=None):
    if conn is not None:
        return _load_venue_master(conn)
    with engine.connect() as connection:
        return _load_venue_master(connection)


def find_venue(name, master):
    """Text containing a known venue returns the venue's master name."""
    normalized = _normalize(name)
    for venue_key, (venue, _) in sorted(master.items(), key=lambda item: len(item[0]), reverse=True):
        if venue_key and venue_key in normalized:
            return venue
    return ""


def get_prefecture(name, master=None):
    """都道府県名または会場マスターから都道府県を取得する。"""
    value = unicodedata.normalize("NFKC", str(name or ""))
    prefectures = (
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
        "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府",
        "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県",
        "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県",
        "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
    )
    for prefecture in prefectures:
        if prefecture in value:
            return prefecture

    normalized = _normalize(value)
    master = _venue_master() if master is None else master
    for venue_key, (_, prefecture) in sorted(master.items(), key=lambda item: len(item[0]), reverse=True):
        if venue_key and venue_key in normalized:
            return prefecture
    return ""
