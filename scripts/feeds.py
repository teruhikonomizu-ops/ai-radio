# -*- coding: utf-8 -*-
"""ラジオ2番組で共用する RSS/Atom 取得・解析ユーティリティ。

このファイルが担当すること:
  ・RSS 2.0 / RSS 1.0(RDF) / Atom の3形式を1つの関数で読む
  ・pubDate / dc:date / atom:updated を日本時間の datetime に直す
  ・「直近◯時間以内」で鮮度を絞る(古い記事を今日のニュースとして読むのを防ぐ)
  ・フィード自体が更新停止していないかを見張る(2026-08-23にNHKのRSS移転で
    半月ぶんの古い見出しを毎朝読み続けていた事故を受けて追加。旧URLは
    HTTP 200 のまま中身だけ2週間前で凍結していた=「静かな故障」だった)

標準ライブラリのみ。
"""
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))
ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"

UA = "Mozilla/5.0 (personal news digest; contact: unizom)"


def now_jst() -> datetime:
    return datetime.now(JST)


def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: str):
    """RFC822(pubDate) と ISO8601(dc:date / atom) の両方を日本時間に直す。読めなければ None。"""
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST)
    except Exception:
        return None


def parse_feed(xml_bytes: bytes):
    """RSS2.0 / RSS1.0(RDF) / Atom を (title, desc, dt) のリストにする。"""
    root = ET.fromstring(xml_bytes)
    out = []
    # RSS 2.0 は <item>、RSS 1.0(RDF) は名前空間つきの <rss1:item>
    nodes = list(root.iter("item")) + list(root.iter(RSS1 + "item"))
    for it in nodes:
        title = strip_html(it.findtext("title") or it.findtext(RSS1 + "title") or "")
        desc = strip_html(it.findtext("description") or it.findtext(RSS1 + "description") or "")
        dt = parse_date(it.findtext("pubDate") or it.findtext(DC + "date") or "")
        if title:
            out.append((title, desc, dt))
    if out:
        return out
    for e in root.iter(ATOM + "entry"):
        title = strip_html(e.findtext(ATOM + "title") or "")
        desc = strip_html(e.findtext(ATOM + "summary") or e.findtext(ATOM + "content") or "")
        dt = parse_date(e.findtext(ATOM + "published") or e.findtext(ATOM + "updated") or "")
        if title:
            out.append((title, desc, dt))
    return out


def norm_title(s: str) -> str:
    """同一記事の取りこぼし判定用。記号・空白を落として比べやすくする。"""
    s = s.translate({c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)})  # 全角英数記号→半角
    s = s.lower()
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", s)


def age_label(dt, now: datetime) -> str:
    """[今日] [昨日] [2日前] … 台本が古い記事を今日の出来事として語るのを防ぐ印。"""
    if dt is None:
        return "日付不明"
    days = (now.date() - dt.date()).days
    if days <= 0:
        return f"今日 {dt.strftime('%H:%M')}"
    if days == 1:
        return f"昨日 {dt.strftime('%H:%M')}"
    return f"{days}日前 {dt.month}/{dt.day}"


def fetch_all(sources):
    """sources = [(表示名, URL), ...] を全部取ってくる(鮮度の絞り込みはしない)。

    戻り値 (groups, stats)
      groups: [(表示名, [ {title, desc, dt} ... ]), ...]
      stats : {"ok":成功数, "total":件数, "ng":[エラー文], "newest":{表示名: 最新記事の日時}}
    """
    groups, ng, newest = [], [], {}
    ok = 0
    for name, url in sources:
        try:
            items = parse_feed(fetch(url))
            ok += 1
        except Exception as e:
            ng.append(f"{name}: {type(e).__name__} {e}")
            continue
        dated = [d for _, _, d in items if d]
        if dated:
            newest[name] = max(dated)
        groups.append((name, [{"title": t, "desc": d, "dt": dt} for t, d, dt in items]))
    return groups, {"ok": ok, "total": len(sources), "ng": ng, "newest": newest}


def select(groups, hours: float, per_source: int, seen: set, keep_undated: bool = False):
    """取得済みの記事から「直近 hours 時間」のものだけ選ぶ。seen で同一記事の重複を防ぐ。

    keep_undated=True のとき、日付が読めなかった記事も拾う(素材不足のときの最後の手段)。
    """
    now = now_jst()
    limit = now - timedelta(hours=hours)
    out = []
    for name, items in groups:
        picked = []
        for it in items:
            dt = it["dt"]
            if dt is None:
                if not keep_undated:
                    continue
            elif dt < limit:
                continue
            key = norm_title(it["title"])
            if not key or key in seen:
                continue
            seen.add(key)
            picked.append(dict(it, label=age_label(dt, now)))
            if len(picked) >= per_source:
                break
        picked.sort(key=lambda x: x["dt"] or datetime(1970, 1, 1, tzinfo=JST), reverse=True)
        if picked:
            out.append((name, picked))
    return out


def check_stale(newest: dict, days: float):
    """最新記事が days 日以上前のフィードを「更新停止の疑い」として返す。"""
    now = now_jst()
    out = []
    for name, dt in sorted(newest.items()):
        age = (now - dt).total_seconds() / 86400
        if age >= days:
            out.append(f"{name}: 最新が{age:.1f}日前({dt.strftime('%Y-%m-%d %H:%M')})")
    return out
