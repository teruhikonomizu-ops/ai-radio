# -*- coding: utf-8 -*-
"""(一度きりの補助) 過去の 概要欄.txt のトピック一覧から放送済み台帳を作る。
これから先は Claude が台本と一緒に「トピック.txt」を出すので、この種まきは初回だけ。
使い方: python3 scripts/_seed_log.py <show> [日数]
"""
import io
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 単独では話題を特定できない大手の名前。これだけでは既報にしない(別のニュースを巻き込むため)
BRAND = set("""google openai anthropic claude chatgpt gemini microsoft apple amazon meta nvidia
deepmind facebook instagram x twitter tiktok youtube slack github aws azure ai llm gpt""".split())

STOP = set("""発表 開発 提供 公開 対応 強化 拡大 実験 発生 分析 専門家 可能性 報告 調査 研究 結果
today 今日 日本 政府 会社 企業 世界 最新 新型 新機能 機能 導入 開始 終了 検討 方針 影響 状況
モデル ニュース サービス ツール ユーザー データ システム プラットフォーム エージェント セキュリティ
億ドル 万人 万円 について による ほか その他 など""".split())

TOPIC = re.compile(r"^\s*(?:[0-9０-９]+[.\.、]|[・･\-\*])\s*(.+)$")


def keys_from(line: str):
    out = []
    # 「台風13号」「GPT-5.6」「Gemini 3.7 Flash」など数字を含む具体名を最優先で拾う
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9]*(?:[ .\-][A-Za-z0-9][A-Za-z0-9.\-]*){0,3}", line):
        w = m.group(0).strip(" .-")
        if len(w) >= 3 and w.lower() not in STOP and w.lower() not in BRAND:
            out.append(w)
    # 数字キーは「台風13号」のように前に語が付くものだけ。「4000億」のような断片は別の記事に誤爆する
    for m in re.finditer(r"[一-鿿ァ-ヴー]{1,4}[0-9０-９]+[号人回件年月日兆億万円ドル台種%％]", line):
        w = m.group(0)
        if len(w) >= 4:
            out.append(w)
    for m in re.finditer(r"[ァ-ヴー]{3,}", line):
        if m.group(0) not in STOP:
            out.append(m.group(0))
    for m in re.finditer(r"[一-鿿]{2,8}", line):
        if m.group(0) not in STOP:
            out.append(m.group(0))
    seen, uniq = set(), []
    for k in out:
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        uniq.append(k)
    return uniq[:5]


show = sys.argv[1]
days = int(sys.argv[2]) if len(sys.argv) > 2 else 6
today = date.today()
entries = []
for i in range(1, days + 1):
    d = (today - timedelta(days=i - 1)).isoformat()
    f = Path(f"radio/{show}/{d}/概要欄.txt")
    if not f.exists():
        continue
    n = 0
    for raw in f.read_text(encoding="utf-8").splitlines():
        m = TOPIC.match(raw)
        if not m:
            continue
        topic = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(topic) < 8:
            continue
        ks = keys_from(topic)
        if len(ks) >= 2:
            entries.append({"date": d, "topic": topic[:60], "keys": ks})
            n += 1
    print(f"{d}: {n}件")
entries.sort(key=lambda e: e["date"], reverse=True)
out = Path(f"radio/{show}/_放送済み.json")
out.write_text(json.dumps({"updated": today.isoformat(), "entries": entries},
                          ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{out} に {len(entries)}件")
