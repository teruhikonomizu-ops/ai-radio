# -*- coding: utf-8 -*-
"""読み方辞書（言葉の読み）を、音声合成の直前に当てる（2026-11-19 のみさん「作ってくれたら嬉しい」）。

エンジン（AivisSpeech）が読み違える言葉（その間→ソノカン、差し色→サシショク 等）を、
エンジンへ渡す文字列だけ正しい読みに置き換える。台本・字幕・スライドの文字は元のまま。
一度辞書に足せば、ラジオ・音声付き資料・読み上げのどれでも二度と直さなくてよい。

  正本 ＝ OneDriveデスクトップ _tools\\tts\\reading_words.json（2台のPCで共有）
  写し ＝ ~\\repos\\ai-radio\\scripts\\reading_words.json と reading_words.py（ラジオはクラウドで動くため）
          写すのは同じフォルダの sync_to_radio.py。正本を直したら必ず回す（README の「読み方辞書」）。

辞書の1件:
  {"書き": "その間", "読み": "そのあいだ", "後に続かない": "違", "メモ": "なぜ足したか"}
  ・書き      … 台本に出てくる表記そのまま（必須）
  ・読み      … ひらがな（またはカタカナ）で書く正しい読み（必須）
  ・前に来ない … この字が直前にある時は置き換えない（1字ずつ並べる。例 "空中" ＝空・中のどちらかが前なら無視）
  ・後に続かない … この文字列（正規表現）が直後に続く時は置き換えない（例 "違" ＝「その間違い」を守る）
  長い書きから先に当てる（1回だけ・置き換えた結果を二度は直さない）。

辞書が無い・壊れている時は置き換えずに続ける（読み替えは補助。番組や資料づくりを止めない）。

確かめ方（エンジンが起動している時）:
  python reading_words.py "その間に差し色を足す"     … 置き換え前後でエンジンの読みを並べて見せる
  python reading_words.py --file 台本.txt             … 辞書が当たった箇所と、置き換え後の読みを表示
  python reading_words.py --selftest                  … 辞書の書き方の検査（エンジン不要）
"""
import json
import re
import sys
from pathlib import Path

DICT_PATH = Path(__file__).with_name("reading_words.json")
# 手元だけの辞書（2026-11-19 別の目の点検 G）: 取引先名・未発表の商品名など、公開の置き場（ラジオ）へ出したくない言葉。
# sync_to_radio.py はこちらを写さない。手元の tts_aivis.py は両方を読む。無ければ何もしない。
LOCAL_PATH = Path(__file__).with_name("reading_words_local.json")


class Table:
    """読み込んだ辞書。pattern が None なら何もしない。"""

    def __init__(self, entries, pattern, errors):
        self.entries = entries
        self.pattern = pattern
        self.errors = errors


def _build(entries):
    errors, good = [], []
    seen = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            errors.append(f"{i + 1}件目: 形が違う")
            continue
        w, r = e.get("書き"), e.get("読み")
        if not (isinstance(w, str) and w.strip() and isinstance(r, str) and r.strip()):
            errors.append(f"{i + 1}件目: 書き・読みが無い")
            continue
        if w in seen:
            errors.append(f"{i + 1}件目: 「{w}」が重複")
            continue
        if re.search(r"[A-Za-zＡ-Ｚａ-ｚ]", r):
            errors.append(f"{i + 1}件目: 「{w}」の読みに英字がある（かなで書く）")
            continue
        before = e.get("前に来ない") or ""
        after = e.get("後に続かない") or ""
        if not isinstance(before, str) or not isinstance(after, str):
            errors.append(f"{i + 1}件目: 「{w}」の前に来ない・後に続かないは文字で書く（配列・数字は不可）")
            continue
        if re.search(r"\(\?P", after):
            errors.append(f"{i + 1}件目: 「{w}」の後に続かないに名前付きの組 (?P は使えない")
            continue
        try:
            pat = ""
            if before:
                pat += "(?<![" + re.escape(before) + "])"
            pat += re.escape(w)
            if after:
                re.compile(after)
                pat += "(?!" + after + ")"
            re.compile(pat)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{i + 1}件目: 「{w}」の条件が読めない（{ex}）")
            continue
        seen.add(w)
        good.append((w, r, pat))
    good.sort(key=lambda t: len(t[0]), reverse=True)  # 長い書きから先に当てる
    pattern = None
    if good:
        try:
            pattern = re.compile("|".join(f"(?P<g{k}>{p})" for k, (_, _, p) in enumerate(good)))
        except Exception as ex:  # noqa: BLE001
            errors.append(f"辞書全体をまとめられない（{ex}）＝置き換えなしで続ける")
            return Table([], None, errors)
    return Table(good, pattern, errors)


def _read_entries(path: Path):
    """(言葉の一覧, 誤り) を返す。無い・壊れている・形が違う時は誤りに積む。"""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        return [], [f"{Path(path).name}: 一番外側が {{ }} の形ではない"]
    entries = data.get("言葉")
    if not isinstance(entries, list):
        return [], [f"{Path(path).name}: 「言葉」の一覧が無い（キー名の打ち間違い・空の値）"]
    return entries, []


def load(path: Path = DICT_PATH, with_local: bool = False) -> Table:
    """辞書を読む。どんな壊れ方でも例外は外へ出さず、置き換えなし（または読めた分だけ）で続ける。
    with_local=True なら手元だけの辞書（reading_words_local.json）も足す（ラジオでは使わない）。"""
    try:
        entries, errors = [], []
        paths = [Path(path)] + ([LOCAL_PATH] if with_local and LOCAL_PATH.exists() else [])
        for p in paths:
            try:
                e, err = _read_entries(p)
            except Exception as ex:  # noqa: BLE001
                e, err = [], [f"{p.name} を読めない（{ex}）"]
            entries += e
            errors += err
        t = _build(entries)
        t.errors = errors + t.errors
    except Exception as ex:  # noqa: BLE001
        t = Table([], None, [f"読み方辞書を読めない（{ex}）"])
    for msg in t.errors:
        print(f"::warning::読み方辞書: {msg}（使わずに続けます）")
    return t


def apply(text: str, table: Table, hits=None) -> str:
    """エンジンへ渡す文字列だけを置き換える。hits に set を渡すと当たった書きを積む。
    万一ここで失敗しても、元の文のまま返す（声づくりを止めない）。"""
    if table is None or getattr(table, "pattern", None) is None or not text:
        return text
    try:
        return _apply(text, table, hits)
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::読み方辞書の置き換えに失敗したので元の文で続けます: {ex}")
        return text


def _apply(text, table, hits):

    def repl(m):
        k = int(m.lastgroup[1:])
        w, r, _ = table.entries[k]
        if hits is not None:
            hits.add(w)
        return r

    return table.pattern.sub(repl, text)


def _engine_kana(text: str) -> str:
    import urllib.parse
    import urllib.request
    base = "http://127.0.0.1:10101"
    spk = json.load(urllib.request.urlopen(base + "/speakers", timeout=10))[0]["styles"][0]["id"]
    req = urllib.request.Request(f"{base}/audio_query?speaker={spk}&text={urllib.parse.quote(text)}", method="POST")
    q = json.load(urllib.request.urlopen(req, timeout=60))
    return "/".join("".join(m["text"] for m in ap["moras"]) for ap in q["accent_phrases"])


def _selftest() -> int:
    t = _build([
        {"書き": "その間", "読み": "そのあいだ", "後に続かない": "違"},
        {"書き": "差し色", "読み": "さしいろ"},
        {"書き": "間", "読み": "ま", "前に来ない": "その空時"},
    ])
    cases = [
        ("その間に差し色を", "そのあいだに さしいろを".replace(" ", "")),
        ("その間違いは", "その間違いは"),      # 後に続かない＝守られる
        ("空間と時間", "空間と時間"),          # 前に来ない＝守られる
        ("間をとる", "まをとる"),
    ]
    bad = 0
    for src, want in cases:
        got = apply(src, t)
        ok = got == want
        bad += not ok
        print(("OK  " if ok else "NG  ") + f"{src} → {got}" + ("" if ok else f"（期待 {want}）"))
    real = load(with_local=True)
    print(f"本物の辞書: {len(real.entries)}件（手元だけの辞書を含む）・書き方の誤り {len(real.errors)}件")
    if not real.entries:
        print("  辞書が0語＝読めていない")
        bad += 1
    for msg in real.errors:
        print("  " + msg)
    return 1 if (bad or real.errors) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == "--selftest":
        raise SystemExit(_selftest())
    table = load(with_local=True)
    if args[0] == "--file":
        hits_all = set()
        for line in Path(args[1]).read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            hits = set()
            out = apply(line, table, hits)
            if hits:
                hits_all |= hits
                print(f"・{line.strip()}\n  → {out.strip()}")
        print(f"当たった言葉: {sorted(hits_all) or 'なし'}")
    else:
        src = " ".join(args)
        out = apply(src, table)
        print(f"元の文 : {src}\n  読み : {_engine_kana(src)}")
        if out != src:
            print(f"辞書後 : {out}\n  読み : {_engine_kana(out)}")
        else:
            print("（辞書に当たる言葉はありません）")
