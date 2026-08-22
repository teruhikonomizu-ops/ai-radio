# -*- coding: utf-8 -*-
"""放送済み台帳 — 「もう放送したニュース」を覚えておき、翌朝の素材から外すための帳簿。

なぜ要るか(2026-08-23):
  RSSは同じ話題を何日も配信し続けるうえ、続報記事も毎日出る。素材をそのまま渡すと
  「台風13号に厳重警戒」「Gemini 3.7 Flash 発表」を7日連続で読み上げてしまう。
  そこで、台本を書いたClaudeに「今日扱ったトピック+キーワード」を出させて貯めておき、
  翌朝の収集時にそれと照合して【既報】の印を付ける。

台帳の場所: radio/<show>/_放送済み.json
  {"entries":[{"date":"2026-08-23","topic":"見出し","keys":["Gemini 3.7 Flash","Google DeepMind"]}, ...]}

使い方:
  python3 broadcast_log.py add <台帳.json> <YYYY-MM-DD> <トピック.txt>
      トピック.txt は1行1トピックで「見出し ||| キーワード1, キーワード2, ...」形式
  python3 broadcast_log.py show <台帳.json> [日数]
"""
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

KEEP_DAYS = 14      # 台帳に残す日数
MATCH_DAYS = 7      # 照合に使う日数(継続案件を永久に封じないよう、貯める期間より短くする)

# 単独では話題を絞れない広すぎる語。これ1つだけでは既報にしない
# (「ウクライナ」1語で既報にすると、その国の別の大きなニュースまで潰してしまう)
BROAD = set("""ウクライナ ロシア アメリカ 中国 韓国 北朝鮮 台湾 イスラエル イラン インド ドイツ フランス
イギリス ヨーロッパ ロシア軍 日本 東京 大阪 政府 首相 大統領 国連 自民党 立憲民主党 国民民主党
気象庁 警察 警視庁 厚生労働省 経済産業省 文部科学省 国土交通省 財務省 外務省 防衛省""".split())


def _norm(s: str) -> str:
    s = s.translate({c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)})  # 全角英数記号→半角
    s = s.lower()
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", s)


def load(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("entries", [])
    except Exception:
        return []


def recent(entries: list, days: int = MATCH_DAYS, today: date = None) -> list:
    today = today or date.today()
    out = []
    for e in entries:
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if 0 <= (today - d).days < days:
            out.append(e)
    return out


def _prepare(entries: list):
    """照合しやすい形に前処理。

    specific = 数字を含む4文字以上、または3語以上のキー(「Gemini 3.7 Flash」「台風13号」「SB 53」)。
               その話題を一意に指すので、単独ヒットで既報とみなす。
    normal   = 4文字以上のキー(「Anthropic」「熊本地震」「Google DeepMind」)。会社名だけで別の話題を
               巻き込まないよう、2つ以上ヒットして初めて既報。
    3文字以下は一般語すぎて誤爆する(「台風」「死者」)ので捨てる。
    """
    prepared = []
    for e in entries:
        keys = []
        for k in e.get("keys", []):
            nk = _norm(k)
            if len(nk) < 4:
                continue
            if k.strip() in BROAD:
                keys.append((nk, False, True))   # 普通のキーとしては使うが、単独では効かせない
                continue
            has_digit = bool(re.search(r"\d", k))
            specific = (has_digit and len(nk) >= 4) or (len(k.split()) >= 3 and len(nk) >= 5)
            keys.append((nk, specific, False))
        if keys:
            prepared.append({"date": e.get("date", ""), "topic": e.get("topic", ""), "keys": keys})
    return prepared


def matcher(entries: list, days: int = MATCH_DAYS, today: date = None):
    """テキストを渡すと、既報なら (放送日, トピック名) を返す関数を作る。新規なら None。"""
    prepared = _prepare(recent(entries, days, today))

    def match(text: str):
        nt = _norm(text)
        if not nt:
            return None
        for e in prepared:
            hits = 0
            specific_hit = False
            solo_ok = 0
            for nk, specific, broad in e["keys"]:
                if not broad:
                    solo_ok += 1
                if nk in nt:
                    hits += 1
                    if specific:
                        specific_hit = True
            # 使えるキーが1つしか無いトピック(「熊本地震」など)は、その1つで既報とみなす。
            # これが無いと、短い一般名詞しか手がかりが無い継続案件を毎日繰り返してしまう。
            if specific_hit or hits >= 2 or (hits == 1 and len(e["keys"]) == 1 and solo_ok == 1):
                return (e["date"], e["topic"])
        return None

    return match


def parse_topics(text: str) -> list:
    """Claudeが出した「見出し ||| キーワード, ...」を [{topic, keys}] にする。"""
    out = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-・*").strip()
        if not line or line.startswith("#"):
            continue
        if "|||" in line:
            topic, keys = line.split("|||", 1)
        elif "|" in line:
            topic, keys = line.split("|", 1)
        else:
            continue
        klist = [k.strip() for k in re.split(r"[,、／/]", keys) if k.strip()]
        topic = topic.strip()
        if topic and klist:
            out.append({"topic": topic, "keys": klist[:6]})
    return out


def add(path, day: str, topics_file) -> int:
    entries = load(path)
    tf = Path(topics_file)
    if not tf.exists():
        print(f"トピックファイルが無い: {tf}(台帳は更新しない)")
        return 0
    topics = parse_topics(tf.read_text(encoding="utf-8"))
    if not topics:
        print("トピックが1件も読めなかった(台帳は更新しない)")
        return 0
    entries = [e for e in entries if e.get("date") != day]     # 同じ日の再実行は上書き
    for t in topics:
        entries.append({"date": day, "topic": t["topic"], "keys": t["keys"]})
    cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    entries = [e for e in entries if e.get("date", "") >= cutoff]
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"updated": day, "entries": entries},
                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"放送済み台帳を更新: {day} に {len(topics)}件を追加 / 台帳合計 {len(entries)}件")
    return len(topics)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "add":
        add(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "show":
        days = int(sys.argv[3]) if len(sys.argv) > 3 else MATCH_DAYS
        for e in recent(load(sys.argv[2]), days):
            print(f"{e['date']}  {e['topic']}  ← {', '.join(e.get('keys', []))}")
    else:
        sys.exit(__doc__)
