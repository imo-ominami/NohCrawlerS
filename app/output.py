import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd

from .venue_master import _venue_master, convert_venue, get_prefecture

EVENT_COLUMNS = [
    "取得経路", "サイト名", "公演日", "都道府県", "公演名", "会場",
    "開演時間", "備考", "公演ID", "掲載URL", "取得日時",
]
MERGED_COLUMNS = ["公演日", "都道府県", "公演名", "会場", "開演時間", "備考", "掲載URL"]


def _normalize_title(title):
    value = unicodedata.normalize("NFKC", str(title)).casefold()
    value = re.sub(r"[※＊*]\s*情報追加.*$", "", value)
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def _merge_events(events, venue_master=None):
    venue_master = _venue_master() if venue_master is None else venue_master
    groups = {}
    for event in events.to_dict("records"):
        title = str(event.get("公演名", "")).strip()
        prefecture = str(event.get("都道府県", "") or "").strip()
        if not prefecture:
            prefecture = get_prefecture(
                f"{title} {event.get('会場', '')} {event.get('掲載URL', '')}",
                venue_master,
            )
        event["都道府県"] = prefecture
        normalized = _normalize_title(title)
        if not normalized:
            continue
        candidates = groups.setdefault((event.get("公演日", ""), prefecture), [])
        group = next((
            item for item in candidates
            if any(SequenceMatcher(None, normalized, _normalize_title(other)).ratio() >= 0.9
                   for other in item["titles"])
        ), None)
        if group is None:
            group = {"titles": [], "events": []}
            candidates.append(group)
        group["titles"].append(title)
        group["events"].append(event)

    merged = []
    for (event_date, prefecture), buckets in groups.items():
        for group in buckets:
            entries = group["events"]
            def unique_values(key):
                return list(dict.fromkeys(
                    str(item.get(key, "")).strip()
                    for item in entries if pd.notna(item.get(key)) and str(item.get(key, "")).strip()
                ))
            venues = [
                convert_venue(value, venue_master)
                for value in unique_values("会場")
            ]
            times = unique_values("開演時間")
            remarks = unique_values("備考")
            for remark in remarks:
                if not venues:
                    venue = convert_venue(remark, venue_master)
                    if venue != remark:
                        venues.append(venue)
                if not times:
                    match = re.search(r"(?:開演(?:時間)?|開始時間)?\s*([0-2]?\d)(?::([0-5]\d)|時(半)?)", remark)
                    if match:
                        times.append(f"{int(match.group(1)):02d}:{match.group(2) or ('30' if match.group(3) else '00')}")
            merged.append({
                "公演日": event_date,
                "都道府県": prefecture,
                "公演名": max(dict.fromkeys(group["titles"]), key=len),
                "会場": " ／ ".join(venues),
                "開演時間": " ／ ".join(times),
                "備考": " ／ ".join(remarks),
                "掲載URL": " ／ ".join(unique_values("掲載URL")),
            })
    return pd.DataFrame(merged, columns=MERGED_COLUMNS).sort_values(
        ["公演日", "都道府県", "公演名"], ignore_index=True
    )
