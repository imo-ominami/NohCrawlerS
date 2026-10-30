import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .venue_master import get_prefecture

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_TIMEOUT = 30
EVENT_COLUMNS = [
    "取得経路", "サイト名", "公演日", "都道府県", "公演名", "会場",
    "開演時間", "備考", "公演ID", "掲載URL", "取得日時",
]


def _source_info(url):
    site_name = urlparse(url).netloc or url
    return {"取得経路": "サイト情報", "サイト名": site_name, "URL": url}


def _get(url, params=None):
    response = requests.get(
        url, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response


def _start_time(text):
    value = unicodedata.normalize("NFKC", str(text or ""))
    match = re.search(r"([0-2]?\d)\s*時\s*(半)?\s*開演", value)
    if match:
        return f"{int(match.group(1)):02d}:{'30' if match.group(2) else '00'}"
    match = re.search(r"([0-2]?\d)[:：]([0-5]\d)", value)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    match = re.search(r"開演\s*([0-2]?\d)\s*時\s*(半)?", value)
    if match:
        return f"{int(match.group(1)):02d}:{'30' if match.group(2) else '00'}"
    return ""


def _event(source, collected_at, **values):
    return {
        "取得経路": source["取得経路"],
        "サイト名": source["サイト名"],
        "公演日": values.get("公演日", ""),
        "都道府県": values.get("都道府県", ""),
        "公演名": values.get("公演名", ""),
        "会場": values.get("会場", ""),
        "開演時間": values.get("開演時間", ""),
        "備考": values.get("備考", ""),
        "公演ID": values.get("公演ID", ""),
        "掲載URL": values.get("掲載URL", source["URL"]),
        "取得日時": collected_at,
    }


def _coocan_details(table):
    lines = [" ".join(line.split()) for line in table.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    values = {}
    labels = {
        "会場": {"場所", "会場", "開催場所"},
        "開演時間": {"時間", "開演時間", "開演"},
    }
    for index, line in enumerate(lines[:-1]):
        key = line.rstrip("：:").strip()
        for field, field_labels in labels.items():
            if key in field_labels:
                values[field] = lines[index + 1]
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        for index, cell in enumerate(cells[:-1]):
            key = cell.get_text(" ", strip=True).rstrip("：:").strip()
            for field, field_labels in labels.items():
                if key in field_labels:
                    values.setdefault(field, cells[index + 1].get_text(" ", strip=True))

    venue = values.get("会場", "")
    venue = venue.strip()
    remarks = ""
    if not venue or not values.get("開演時間"):
        rows = table.find_all("tr", recursive=False)
        if len(rows) > 1:
            title = rows[1].find("b")
            following = title.find_next("table") if title else None
            first_cell = following.find("tr").find(["td", "th"]) if following and following.find("tr") else None
            if first_cell:
                remarks = " ".join(first_cell.get_text(" ", strip=True).split())
    return venue, _start_time(values.get("開演時間", "")), remarks


def _crawl_coocan(source, collected_at):
    results = []
    now = datetime.now()
    for offset in range(12):
        month_index = now.year * 12 + now.month - 1 + offset
        year, month = month_index // 12, month_index % 12 + 1
        response = _get(source["URL"], {"cm": "", "mode": "", "year": year, "mon": month})
        soup = BeautifulSoup(response.content.decode("shift_jis", errors="replace"), "html.parser")
        details = {}
        for anchor in soup.find_all("a", attrs={"name": True}):
            table = anchor.find_next("table")
            if anchor.get("name") and table:
                details[anchor["name"]] = _coocan_details(table)

        month_results = []
        for table in soup.find_all("table"):
            for day_row in table.find_all("tr", recursive=False):
                cells = day_row.find_all(["td", "th"], recursive=False)
                if len(cells) < 3:
                    continue
                day = cells[0].get_text(strip=True)
                weekday = cells[1].get_text(strip=True)
                if not day.isdigit() or weekday not in "月火水木金土日":
                    continue
                for event_row in cells[2].find_all("tr"):
                    event_cells = event_row.find_all(["td", "th"], recursive=False)
                    if len(event_cells) < 3:
                        continue
                    prefecture = event_cells[1].get_text(" ", strip=True)
                    title_cell = event_cells[2]
                    link = title_cell.find("a", href=True)
                    event_id = urlsplit(link["href"]).fragment if link else ""
                    event_url = urljoin(response.url, link["href"]) if link else response.url
                    if link:
                        link.decompose()
                    title = " ".join(title_cell.get_text(" ", strip=True).split())
                    if not prefecture or not title:
                        continue
                    venue, start_time, remarks = details.get(event_id, ("", "", ""))
                    month_results.append(_event(
                        source, collected_at, 公演日=f"{year:04d}-{month:02d}-{int(day):02d}",
                        都道府県=prefecture, 公演名=title, 会場=venue,
                        開演時間=start_time, 備考=remarks, 公演ID=event_id,
                        掲載URL=event_url,
                    ))
            if month_results:
                break
        results.extend(month_results)
    return results


def _schema_event_objects(value):
    if isinstance(value, dict):
        event_types = value.get("@type", [])
        if isinstance(event_types, str):
            event_types = [event_types]
        if any(str(item).rsplit("/", 1)[-1].endswith("Event") for item in event_types):
            yield value
        for child in value.values():
            yield from _schema_event_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _schema_event_objects(child)


def _schema_location(event):
    locations = event.get("location", [])
    if not isinstance(locations, list):
        locations = [locations]
    for location in locations:
        if isinstance(location, dict):
            address = location.get("address", {})
            region = address.get("addressRegion", "") if isinstance(address, dict) else ""
            return region, location.get("name", "")
    return "", ""


def _crawl_structured_events(source, collected_at):
    response = _get(source["URL"])
    soup = BeautifulSoup(response.content, "html.parser")
    results = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except json.JSONDecodeError:
            continue
        for event in _schema_event_objects(data):
            name = str(event.get("name", "")).strip()
            try:
                date = datetime.strptime(str(event.get("startDate", ""))[:10], "%Y-%m-%d").date().isoformat()
            except ValueError:
                continue
            if not name:
                continue
            region, venue = _schema_location(event)
            start_date = str(event.get("startDate", ""))
            time_match = re.search(r"T([0-2]?\d:[0-5]\d)", start_date)
            venue = str(venue or "").strip()
            prefecture = str(region or "").strip()
            if not prefecture.endswith(("県", "都", "府", "道")):
                prefecture = get_prefecture(f"{name} {venue}", {})
            results.append(_event(
                source, collected_at, 公演日=date,
                都道府県=prefecture,
                公演名=name, 会場=venue,
                開演時間=time_match.group(1) if time_match else "",
                公演ID=str(event.get("@id", "")),
                掲載URL=urljoin(source["URL"], str(event.get("url") or source["URL"])),
            ))
    return results


def _crawl_the_noh_month(url, source, collected_at):
    response = _get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    month_match = re.search(r"/(\d{4})/(\d{1,2})/?$", urlparse(response.url).path)
    if not month_match:
        return []
    year, default_month = map(int, month_match.groups())
    results = []
    for heading in soup.select("h3.entry-header"):
        dates = []
        month = default_month
        for match in re.finditer(r"(?:(\d{1,2})月\s*)?(\d{1,2})日", heading.get_text(" ", strip=True)):
            if match.group(1):
                month = int(match.group(1))
            dates.append((month, int(match.group(2))))
        card = heading.parent
        content = card.select_one(".entry-content .basetext")
        if not dates or content is None:
            continue
        events = []
        name, links = "", []
        for paragraph in content.find_all("p"):
            strong = paragraph.find("strong")
            paragraph_links = [urljoin(response.url, a["href"]) for a in paragraph.find_all("a", href=True)]
            if strong and paragraph.get_text(strip=True):
                if name:
                    events.append((name, links))
                name = " ".join(strong.get_text(" ", strip=True).split())
                links = paragraph_links
            elif name:
                links.extend(paragraph_links)
        if name:
            events.append((name, links))
        for event_index, (name, event_links) in enumerate(events, start=1):
            match = re.search(r"([0-2]?\d[:：][0-5]\d)\s*[～〜~]", name)
            start_time = match.group(1).replace("：", ":") if match else _start_time(name)
            venue = name[match.end():].strip(" 　、,，") if match else ""
            for event_month, day in dates:
                try:
                    event_date = datetime(year, event_month, day).date().isoformat()
                except ValueError:
                    continue
                event_id = card.get("id", "")
                if event_index > 1:
                    event_id = f"{event_id}-{event_index}"
                results.append(_event(
                    source, collected_at, 公演日=event_date,
                    都道府県=get_prefecture(f"{name} {venue}", {}),
                    公演名=name, 会場=venue, 開演時間=start_time,
                    公演ID=event_id, 掲載URL=event_links[0] if event_links else response.url,
                ))
    return results


def _crawl_the_noh(source, collected_at):
    parsed = urlparse(source["URL"])
    if re.search(r"/\d{4}/\d{1,2}/?$", parsed.path):
        return _crawl_the_noh_month(source["URL"], source, collected_at)
    response = _get(source["URL"])
    soup = BeautifulSoup(response.content, "html.parser")
    month_urls = list(dict.fromkeys(
        urljoin(response.url, anchor["href"])
        for anchor in soup.find_all("a", href=True)
        if re.search(r"/jp/schedule/[^/]+/\d{4}/\d{1,2}/?$",
                     urlparse(urljoin(response.url, anchor["href"])).path)
    ))
    return [
        event
        for month_url in month_urls
        for event in _crawl_the_noh_month(month_url, source, collected_at)
    ]


def get_data(url):
    """サイト情報シートに登録されたURLから公演情報を取得する。"""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"URLはhttpまたはhttpsで指定してください: {url}")
    source = _source_info(url)
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if parsed.hostname == "nohgaku.fan.coocan.jp" and parsed.path.endswith("/schedule/sche36.cgi"):
        data = _crawl_coocan(source, collected_at)
    elif parsed.hostname == "www.the-noh.com" and parsed.path.startswith("/jp/schedule/"):
        data = _crawl_the_noh(source, collected_at)
    else:
        data = _crawl_structured_events(source, collected_at)
    return pd.DataFrame(data, columns=EVENT_COLUMNS).to_dict("records")
