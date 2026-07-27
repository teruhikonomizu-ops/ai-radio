# -*- coding: utf-8 -*-
"""ニュースラジオ用: 公式RSSから今日のニュース見出しを収集し、コンパクトなダイジェストを出力する。
使い方: python collect_news.py > digest.md  (または引数に出力先パス)
外部ライブラリ不要(標準ライブラリのみ)。取得先は各社の公式RSS(規約上安全なルート)のみ。
"""
import sys
import io
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 公式RSS(見出し+短い説明のみが配信される。本文は取得しない=著作権安全側)
SOURCES = [
    ("NHK 主要",   "https://www3.nhk.or.jp/rss/news/cat0.xml"),
    ("NHK 国際",   "https://www3.nhk.or.jp/rss/news/cat6.xml"),
    ("NHK 政治",   "https://www3.nhk.or.jp/rss/news/cat4.xml"),
    ("NHK 経済",   "https://www3.nhk.or.jp/rss/news/cat5.xml"),
    ("NHK 社会",   "https://www3.nhk.or.jp/rss/news/cat1.xml"),
    ("Yahoo 主要", "https://news.yahoo.co.jp/rss/topics/top-picks.xml"),
    ("Yahoo 国際", "https://news.yahoo.co.jp/rss/topics/world.xml"),
    ("Yahoo 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo 経済", "https://news.yahoo.co.jp/rss/topics/business.xml"),
    ("Yahoo IT",  "https://news.yahoo.co.jp/rss/topics/it.xml"),
]

MAX_ITEMS = 12  # 1ソースあたり上限(トークン節約)

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal news digest)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def parse_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            yield title, desc, pub

def main():
    out = sys.stdout if len(sys.argv) < 2 else open(sys.argv[1], "w", encoding="utf-8")
    print(f"# ニュースダイジェスト {datetime.now().strftime('%Y-%m-%d %H:%M')}", file=out)
    ok, ng = 0, []
    for name, url in SOURCES:
        try:
            items = list(parse_items(fetch(url)))[:MAX_ITEMS]
            ok += 1
        except Exception as e:
            ng.append(f"{name}: {e}")
            continue
        print(f"\n## {name}", file=out)
        for title, desc, pub in items:
            line = f"- {title}"
            if desc:
                line += f" — {desc[:120]}"
            print(line, file=out)
    if ng:
        print("\n## 取得失敗", file=out)
        for n in ng:
            print(f"- {n}", file=out)
    print(f"\n(取得成功 {ok}/{len(SOURCES)} ソース)", file=out)
    if out is not sys.stdout:
        out.close()

if __name__ == "__main__":
    main()
