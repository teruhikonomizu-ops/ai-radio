# -*- coding: utf-8 -*-
"""Claudeの出力を 台本 / 概要欄 / トピック台帳 に分割し、文字数・タイトル長を検査する。
使い方: python3 split_output.py <claude出力> <台本> <概要欄> [最小字数] [最大字数] [トピック出力] [厳格=1/0]
不合格なら <claude出力と同じフォルダ>/feedback.txt に修正指示を書き、exit 3。
字数は「#コメント行と空白を除いた、実際に読み上げられる文字数」で数える。

トピック台帳(2026-08-23追加)は「見出し ||| キーワード, ...」の一覧で、放送済み台帳に貯めて
翌朝の重複排除に使う。厳格=1(1回目の試行)では欠けていたら作り直させ、0(2回目以降)では警告だけ。
"""
import re
import sys
from pathlib import Path

src, dst_script, dst_desc = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
lo = int(sys.argv[4]) if len(sys.argv) > 4 else 2600
hi = int(sys.argv[5]) if len(sys.argv) > 5 else 3400
dst_topics = Path(sys.argv[6]) if len(sys.argv) > 6 else src.parent / "topics.txt"
strict = (sys.argv[7] if len(sys.argv) > 7 else "1") == "1"
text = src.read_text(encoding="utf-8")


def extract(name: str, required=True) -> str:
    m = re.search(rf"===\s*{name}ここから\s*===\s*\n(.*?)\n\s*===\s*{name}ここまで\s*===", text, re.S)
    if not m:
        if required:
            sys.exit(f"出力に『==={name}ここから===』〜『==={name}ここまで===』の区切りが見つからない")
        return ""
    body = m.group(1).strip()
    body = re.sub(r"^```[a-z]*\n|\n```$", "", body)  # 万一のコードフェンス除去
    return body + "\n"


script = extract("台本")
desc = extract("概要欄")
topics = extract("トピック台帳", required=False)

spoken = "\n".join(l for l in script.splitlines() if not l.startswith("#"))
spoken = re.sub(r"^(ユー|ゼータ):\s*", "", spoken, flags=re.M)  # 話者タグは読み上げられないので字数に含めない
chars = len(re.sub(r"\s", "", spoken))
title = desc.splitlines()[0].strip()
topic_lines = [l for l in topics.splitlines()
               if "|||" in l and len(re.split(r"[,、／/]", l.split("|||", 1)[1])) >= 2]
print(f"台本(読み上げ分) {chars}字 / タイトル {len(title)}字 / トピック {len(topic_lines)}件: {title}")

problems = []
if not (lo <= chars <= hi):
    problems.append(
        f"台本の読み上げ文字数が{chars}字で、許容範囲({lo}〜{hi}字)の外だった。"
        f"{lo}〜{hi}字になるようニュースの本数・詳しさを調整して全体を作り直すこと。"
        "同じ話を言い換えて繰り返す水増しはしないこと。"
    )
if len(title) > 40:
    problems.append(f"概要欄1行目のタイトルが{len(title)}字だった。40字以内に収めること。")
if len(topic_lines) < 4:
    msg = (f"トピック台帳が{len(topic_lines)}件しか読み取れなかった。"
           "『===トピック台帳ここから===』〜『===トピック台帳ここまで===』の中に、"
           "台本で扱った話題を1行1件で『見出し ||| キーワード1, キーワード2, キーワード3』の形で"
           "4件以上書くこと(キーワードは各2個以上・その話題を一意に特定できる固有名詞)。")
    if strict:
        problems.append(msg)
    else:
        print("警告: " + msg, file=sys.stderr)

if problems:
    (src.parent / "feedback.txt").write_text("\n".join(problems) + "\n", encoding="utf-8")
    print("\n".join(problems), file=sys.stderr)
    sys.exit(3)

dst_script.write_text(script, encoding="utf-8")
dst_desc.write_text(desc, encoding="utf-8")
dst_topics.write_text("\n".join(topic_lines) + "\n" if topic_lines else "", encoding="utf-8")
print("分割OK")
