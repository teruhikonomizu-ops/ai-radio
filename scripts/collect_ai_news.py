# -*- coding: utf-8 -*-
"""AIテックラジオ用: AI・テクノロジーの公式RSS/Atomから見出し+要旨を収集しダイジェスト出力。
海外(英語)一次情報＋国内AI媒体。本文は取得しない=著作権安全側。台本側で日本語に要約する。

使い方:
  python3 collect_ai_news.py work/digest.md [--log radio/tech/_放送済み.json]
                                             [--also-log radio/news/_放送済み.json]
                                             [--hours 60] [--min-new 18]
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import build_digest

# 主力。末尾(en)=英語で翻訳が要る / (ja)=日本語
MAIN = [
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

# 予備(新規が目標本数に届かない朝だけ足す)
BACKUP = [
    ("Hugging Face (en)",   "https://huggingface.co/blog/feed.xml"),
    ("Google Research (en)","https://research.google/blog/rss/"),
    ("AWS ML Blog (en)",    "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("NVIDIA Blog (en)",    "https://blogs.nvidia.com/feed/"),
    ("WIRED AI (en)",       "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("ZDNET AI (en)",       "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"),
    ("MIT News AI (en)",    "https://news.mit.edu/rss/topic/artificial-intelligence2"),
    ("Simon Willison (en)", "https://simonwillison.net/atom/everything/"),
    ("Publickey (ja)",      "https://www.publickey1.jp/atom.xml"),
    ("CNET Japan (ja)",     "https://feeds.japan.cnet.com/rss/cnet/all.rdf"),
    ("PC Watch (ja)",       "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf"),
    ("ITmedia NEWS (ja)",   "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
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
        "AIニュース", MAIN, BACKUP, out,
        hours=float(opts.get("--hours", 60)),   # 企業ブログは毎日は出ないので国内ニュースより広め
        min_new=int(opts.get("--min-new", 18)),
        per_source=int(opts.get("--per-source", 10)),
        max_total=int(opts.get("--max-total", 65)),
        desc_len=160,
        stale_days=10,    # 企業の公式ブログは1週間出ないこともある。故障判定は緩め
        logs=logs,
    )


if __name__ == "__main__":
    main()
