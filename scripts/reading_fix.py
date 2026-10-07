# -*- coding: utf-8 -*-
"""音声合成の直前に、台本に残った英字をカタカナの読みに置き換える(2026-10-07追加)。

台本の執筆ルール(prompts/*.md)で「英字はカタカナに」と指示しているが、AIが守り切れず
9/16〜29の台本28本中15本に英字が残っていた(AI・CNN・NEC・NISA 等)。指示だけに頼らず、
エンジンへ渡す文字列だけをここで機械的に直す。台本.txt と字幕(segments.json)は元の表記のまま。

  1. reading_dict.json にある語 → 辞書の読み(大文字小文字を区別して先に探し、無ければ大文字で探す)
  2. 辞書に無い「大文字の略語・1文字」 → 1文字ずつ読む(CNN → シーエヌエヌ)。ただし
     4文字以上で母音を含む大文字語(NASA 等)とローマ数字(III)は読み替えずエンジンに任せる
  3. 辞書に無い普通の英単語(Anthropic 等) → 置き換えず、unknown に積んでログに出す
     (読みを推測で作ると、間違った読みを自信満々で放送するため)
"""
import json
import re
from pathlib import Path

DICT_PATH = Path(__file__).with_name("reading_dict.json")

LETTERS = {
    "A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "イー", "F": "エフ", "G": "ジー",
    "H": "エイチ", "I": "アイ", "J": "ジェー", "K": "ケー", "L": "エル", "M": "エム", "N": "エヌ",
    "O": "オー", "P": "ピー", "Q": "キュー", "R": "アール", "S": "エス", "T": "ティー", "U": "ユー",
    "V": "ブイ", "W": "ダブリュー", "X": "エックス", "Y": "ワイ", "Z": "ゼット",
}
# 全角英字は半角にそろえてから処理する
_ZEN = str.maketrans({chr(0xFF21 + i): chr(0x41 + i) for i in range(26)} |
                     {chr(0xFF41 + i): chr(0x61 + i) for i in range(26)})
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.&+\-'][A-Za-z0-9]+)*")


def load_dict(path: Path = DICT_PATH) -> dict:
    """辞書が無い・壊れている時は空の辞書で続ける(読み替えは補助。番組を止めない)"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, str) and not k.startswith("_")}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::読み辞書 {path.name} を読めなかったので、読み替えは略語の1文字読みだけで続けます: {e}")
        return {}


def _spell(word: str) -> str:
    """大文字の略語を1文字ずつ読む。数字は数字のまま残す(エンジンが読む)"""
    return "".join(LETTERS.get(ch.upper(), ch) for ch in word)


def fix(text: str, table: dict, unknown: set) -> str:
    text = text.translate(_ZEN)

    def lookup(w):
        if w in table:
            return table[w]
        if w.upper() in table:
            return table[w.upper()]
        return None

    def repl(m):
        w = m.group(0)
        hit = lookup(w)
        if hit is not None:
            return hit
        # iPhone17・Switch2 のように数字が続く語は、英字部分で辞書を引く
        m2 = re.fullmatch(r"([A-Za-z][A-Za-z\-]*?)-?([0-9]+)", w)
        if m2 and lookup(m2.group(1)) is not None:
            return lookup(m2.group(1)) + m2.group(2)
        letters = re.sub(r"[^A-Za-z]", "", w)
        if len(letters) >= 2 and re.fullmatch(r"[IVX]+", letters):
            return w                       # ローマ数字(第III章)はエンジンに任せる
        if letters.isupper() and len(letters) >= 4 and re.search(r"[AEIOU]", letters):
            unknown.add(w)                 # NASA・SONY のように単語として読む略語かもしれない
            return w
        if letters.isupper() or len(letters) == 1:
            # 略語は1文字ずつ読む。GPT-5・USB-C の「-」は読まない
            return re.sub(r"[A-Za-z]+", lambda x: _spell(x.group(0)), w.replace("-", ""))
        unknown.add(w)
        return w

    return TOKEN.sub(repl, text)


if __name__ == "__main__":
    # 動作確認: python reading_fix.py 台本.txt ...  → 置き換え後に英字が残る行と未登録語を表示
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    table = load_dict()
    unknown: set = set()
    left = 0
    for p in sys.argv[1:]:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            body = re.sub(r"^(ユー|ゼータ):\s*", "", line)
            out = fix(body, table, unknown)
            if re.search(r"[A-Za-z]", out):
                left += 1
    print(f"英字が残った行: {left} / 辞書に無い英単語: {sorted(unknown)}")
