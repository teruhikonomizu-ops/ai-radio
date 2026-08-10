# -*- coding: utf-8 -*-
"""radio/<show>/*/meta.json から docs/<show>/feed.xml (ポッドキャストRSS)を生成する。
使い方: python3 make_feed.py <show>
このフィードURLをスマホのポッドキャストアプリ(またはSpotify等)に登録すると、
新しいエピソードが自動で配信される。
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

JST = timezone(timedelta(hours=9))
repo = os.environ.get("GITHUB_REPOSITORY", "teruhikonomizu-ops/ai-radio")
owner, name = repo.split("/")
PAGES = f"https://{owner}.github.io/{name}"

SHOWS = {
    "news": {
        "title": "AIデイリーニュース",
        "description": "AIがNHKニュース・Yahoo!ニュースの公式RSS見出しをもとに要約し、"
                       "AIアンドロイドのユーがAI音声でお届けする約10分のデイリーニュース。"
                       "毎朝5時ごろ自動更新。",
        "author": "unizom",
        "category": "News",
        "pub_hour": 5,
    },
    "tech": {
        "title": "世界のAIニュース",
        "description": "世界のAI・テクノロジーの最新ニュースをAIが日本語で要約し、"
                       "相棒ロボットのゼータがAI音声でお届けする約10分の番組。"
                       "毎朝4時ごろ自動更新。",
        "author": "unizom",
        "category": "Technology",
        "pub_hour": 4,
    },
}

show = sys.argv[1]
cfg = SHOWS[show]

episodes = []
for meta_file in sorted(Path(f"radio/{show}").glob("*/meta.json"), reverse=True):
    episodes.append(json.loads(meta_file.read_text(encoding="utf-8")))


def rfc2822(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=cfg["pub_hour"], tzinfo=JST)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def hms(sec: int) -> str:
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


items = []
for e in episodes:
    items.append(f"""    <item>
      <title>{escape(e["title"])}</title>
      <description>{escape(e["description"])}</description>
      <pubDate>{rfc2822(e["date"])}</pubDate>
      <guid isPermaLink="false">{escape(e["url"])}</guid>
      <enclosure url="{escape(e["url"])}" length="{e["size_bytes"]}" type="audio/mpeg"/>
      <itunes:duration>{hms(e["duration_sec"])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(cfg["title"])}</title>
    <link>{PAGES}/</link>
    <description>{escape(cfg["description"])}</description>
    <language>ja</language>
    <atom:link href="{PAGES}/{show}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{escape(cfg["author"])}</itunes:author>
    <itunes:image href="{PAGES}/{show}/artwork.png"/>
    <itunes:category text="{cfg["category"]}"/>
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
"""

out = Path(f"docs/{show}/feed.xml")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(feed, encoding="utf-8")
print(f"feed.xml 更新: {len(episodes)}エピソード → {out}")
