# -*- coding: utf-8 -*-
"""ニュースラジオ用: 公式RSSから今日のニュースを集め、ダイジェストを出力する。
本文は取得せず、公式配信の見出し+要旨だけを使う(著作権の安全側)。

使い方:
  python3 collect_news.py work/digest.md [--log radio/news/_放送済み.json]
                                          [--also-log radio/tech/_放送済み.json]
                                          [--hours 36] [--min-new 20]

2026-08-23: NHKのRSSが www3.nhk.or.jp → www.nhk.or.jp へ移転していたのに旧URLが
HTTP 200 のまま8月8日の内容で凍結しており、半月ぶんの古い見出しを毎朝「今日のニュース」
として読み上げていた。URLを直すと同時に、鮮度フィルタ・放送済み台帳・更新停止の検知を入れた。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import build_digest

# 主力(毎日ここから作る)
MAIN = [
    ("NHK 主要",   "https://www.nhk.or.jp/rss/news/cat0.xml"),
    ("NHK 国際",   "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("NHK 政治",   "https://www.nhk.or.jp/rss/news/cat4.xml"),
    ("NHK 経済",   "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("NHK 社会",   "https://www.nhk.or.jp/rss/news/cat1.xml"),
    ("NHK 科学医療", "https://www.nhk.or.jp/rss/news/cat3.xml"),
    ("NHK 暮らし",  "https://www.nhk.or.jp/rss/news/cat2.xml"),
    ("Yahoo 主要", "https://news.yahoo.co.jp/rss/topics/top-picks.xml"),
    ("Yahoo 国際", "https://news.yahoo.co.jp/rss/topics/world.xml"),
    ("Yahoo 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo 経済", "https://news.yahoo.co.jp/rss/topics/business.xml"),
    ("Yahoo 科学", "https://news.yahoo.co.jp/rss/topics/science.xml"),
    ("Yahoo 地域", "https://news.yahoo.co.jp/rss/topics/local.xml"),
    ("Yahoo IT",  "https://news.yahoo.co.jp/rss/topics/it.xml"),
]

# 予備(新規が目標本数に届かない朝だけ足す)
BACKUP = [
    ("NHK スポーツ",  "https://www.nhk.or.jp/rss/news/cat7.xml"),
    ("Yahoo スポーツ", "https://news.yahoo.co.jp/rss/topics/sports.xml"),
    ("Yahoo エンタメ", "https://news.yahoo.co.jp/rss/topics/entertainment.xml"),
    ("時事通信",      "https://www.jiji.com/rss/ranking.rdf"),
    ("ITmedia NEWS", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
    ("CNET Japan",   "https://feeds.japan.cnet.com/rss/cnet/all.rdf"),
    ("東洋経済",      "https://toyokeizai.net/list/feed/rss"),
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            opts[sys.argv[i]] = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    out = args[0] if args else "work/digest.md"
    logs = [p for p in (opts.get("--log"), opts.get("--also-log")) if p]
    build_digest.run(
        "ニュース", MAIN, BACKUP, out,
        hours=float(opts.get("--hours", 36)),
        min_new=int(opts.get("--min-new", 20)),
        per_source=int(opts.get("--per-source", 10)),
        max_total=int(opts.get("--max-total", 70)),
        desc_len=120,
        stale_days=3,     # 国内ニュースは毎日出る。3日新着が無ければフィードの故障を疑う
        logs=logs,
    )


if __name__ == "__main__":
    main()
