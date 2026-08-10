# -*- coding: utf-8 -*-
"""Claudeの出力を台本と概要欄に分割し、文字数・タイトル長を検査する。
使い方: python3 split_output.py <claude出力> <台本の出力先> <概要欄の出力先> [最小字数] [最大字数]
不合格なら <claude出力と同じフォルダ>/feedback.txt に修正指示を書き、exit 3。
字数は「#コメント行と空白を除いた、実際に読み上げられる文字数」で数える。
"""
import re
import sys
from pathlib import Path

src, dst_script, dst_desc = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
lo = int(sys.argv[4]) if len(sys.argv) > 4 else 2600
hi = int(sys.argv[5]) if len(sys.argv) > 5 else 3400
text = src.read_text(encoding="utf-8")


def extract(name: str) -> str:
    m = re.search(rf"===\s*{name}ここから\s*===\s*\n(.*?)\n\s*===\s*{name}ここまで\s*===", text, re.S)
    if not m:
        sys.exit(f"出力に『==={name}ここから===』〜『==={name}ここまで===』の区切りが見つからない")
    body = m.group(1).strip()
    body = re.sub(r"^```[a-z]*\n|\n```$", "", body)  # 万一のコードフェンス除去
    return body + "\n"


script = extract("台本")
desc = extract("概要欄")

spoken = "\n".join(l for l in script.splitlines() if not l.startswith("#"))
spoken = re.sub(r"^(ソラ|ピコ):\s*", "", spoken, flags=re.M)  # 話者タグは読み上げられないので字数に含めない
chars = len(re.sub(r"\s", "", spoken))
title = desc.splitlines()[0].strip()
print(f"台本(読み上げ分) {chars}字 / タイトル {len(title)}字: {title}")

problems = []
if not (lo <= chars <= hi):
    problems.append(
        f"台本の読み上げ文字数が{chars}字で、許容範囲({lo}〜{hi}字)の外だった。"
        "2,900〜3,200字(約10分)になるようニュースの本数・詳しさを調整して全体を作り直すこと。"
    )
if len(title) > 40:
    problems.append(f"概要欄1行目のタイトルが{len(title)}字だった。40字以内に収めること。")

if problems:
    (src.parent / "feedback.txt").write_text("\n".join(problems) + "\n", encoding="utf-8")
    print("\n".join(problems), file=sys.stderr)
    sys.exit(3)

dst_script.write_text(script, encoding="utf-8")
dst_desc.write_text(desc, encoding="utf-8")
print("分割OK")
