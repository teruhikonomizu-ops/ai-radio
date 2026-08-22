# -*- coding: utf-8 -*-
"""収集ダイジェストの品質検査。
  ・RSS取得成功が半分未満なら exit 1 で生成を中止する
  ・新規の本数が少なすぎるとき、更新の止まったフィードがあるときは警告を出す
    (2026-08-23: NHKのRSS移転で旧URLがHTTP 200のまま2週間前の内容を返し続け、
     古い見出しを毎朝「今日のニュース」として放送していた。同じ静かな故障を早く見つけるため)
使い方: python3 check_digest.py <digest.md>
"""
import io
import re
import sys

text = io.open(sys.argv[1], encoding="utf-8").read()

m = re.search(r"\(取得成功 (\d+)/(\d+) ソース\)", text)
if not m:
    sys.exit("digest.md に取得成功行が見つからない(収集スクリプトの出力形式を確認)")
ok, total = int(m.group(1)), int(m.group(2))
print(f"RSS取得: {ok}/{total} ソース成功")
if ok * 2 < total:
    sys.exit(f"取得成功が半分未満({ok}/{total})のため、ルールどおり生成を中止")

m2 = re.search(r"\(新規 (\d+)本 / 既報 (\d+)本 / 更新停止疑い (\d+)件\)", text)
if not m2:
    print("::warning::新規/既報の集計行が見つからない(収集スクリプトが古い可能性)")
    sys.exit(0)
fresh, seen, stale = (int(x) for x in m2.groups())
print(f"素材: 新規 {fresh}本 / 既報 {seen}本 / 更新停止疑い {stale}件")

if stale:
    for line in re.findall(r"^  - (.+: 最新が.+)$", text, re.M):
        print(f"::warning::更新が止まっているフィードがある。URLの移転・廃止を疑うこと → {line}")

if fresh == 0:
    sys.exit("新規の素材が0本。全部が既報か、収集が壊れている。放送を中止して原因を調べること")
if fresh < 8:
    print(f"::warning::新規の素材が{fresh}本しかない。番組が薄くなる恐れがある")
