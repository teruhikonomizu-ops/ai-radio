# -*- coding: utf-8 -*-
"""AIテックラジオ用: AI・テクノロジーの公式RSS/Atomから見出し+要旨を収集しダイジェスト出力。
海外(英語)一次情報＋国内AI媒体。本文は取得しない=著作権安全側。台本側で日本語に要約する。
使い方: python collect_ai_news.py > digest.md  (または引数に出力先パス)
標準ライブラリのみ。RSS2.0(item) と Atom(entry) の両方に対応。
"""
import sys
import io
import re
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 公式フィード(見出し+要旨のみ利用)。末尾(en)=英語で翻訳が要る / (ja)=日本語
SOURCES = [
    # --- 海外・企業公式(一次情報) ---
    ("OpenAI (en)",         "https://openai.com/news/rss.xml"),
    ("Google Blog AI (en)", "https://blog.google/technology/ai/rss/"),
    ("Google DeepMind (en)","https://deepmind.google/blog/rss.xml"),
    # --- 海外・専門メディア ---
    ("TechCrunch AI (en)",  "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI (en)",   "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica (en)",   "https://feeds.arstechnica.com/arstechnica/index"),
    ("MIT Tech Review (en)","https://www.technologyreview.com/feed/"),
    ("VentureBeat AI (en)", "https://venturebeat.com/category/ai/feed/"),
    # --- 国内(日本語) ---
    ("ITmedia AI＋ (ja)",   "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("GIGAZINE (ja)",       "https://gigazine.net/news/rss_2.0/"),
    ("Yahoo IT (ja)",       "https://news.yahoo.co.jp/rss/topics/it.xml"),
]

MAX_ITEMS = 10          # 1ソースあたり上限(トークン節約)
DESC_LEN = 160          # 要旨の切り出し長(翻訳・要約の材料。英語は少し長めに)
ATOM = "{http://www.w3.org/2005/Atom}"

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal AI news digest)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)          # タグ除去
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)  # 実体参照除去
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def parse_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    items = list(root.iter("item"))         # RSS 2.0 / RDF
    if items:
        for it in items:
            title = strip_html(it.findtext("title") or "")
            desc = strip_html(it.findtext("description") or "")
            pub = (it.findtext("pubDate") or "").strip()
            if title:
                yield title, desc, pub
        return
    for e in root.iter(ATOM + "entry"):     # Atom
        title = strip_html(e.findtext(ATOM + "title") or "")
        summ = e.findtext(ATOM + "summary") or e.findtext(ATOM + "content") or ""
        desc = strip_html(summ)
        pub = (e.findtext(ATOM + "updated") or e.findtext(ATOM + "published") or "").strip()
        if title:
            yield title, desc, pub

def main():
    if len(sys.argv) >= 2:
        os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)
        out = open(sys.argv[1], "w", encoding="utf-8")
    else:
        out = sys.stdout
    print(f"# AIニュースダイジェスト {datetime.now().strftime('%Y-%m-%d %H:%M')}", file=out)
    print("# (en)=英語ソース=台本で日本語に要約 / (ja)=日本語ソース", file=out)
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
                line += f" — {desc[:DESC_LEN]}"
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
