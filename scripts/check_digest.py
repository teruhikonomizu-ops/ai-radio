# -*- coding: utf-8 -*-
"""収集ダイジェストの品質検査。RSS取得成功が半分未満なら exit 1 で生成を中止する。
使い方: python3 check_digest.py <digest.md>
"""
import io
import re
import sys

text = io.open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"\(取得成功 (\d+)/(\d+) ソース\)", text)
if not m:
    sys.exit("digest.md に取得成功行が見つからない(collect_news.py の出力形式を確認)")
ok, total = int(m.group(1)), int(m.group(2))
print(f"RSS取得: {ok}/{total} ソース成功")
if ok * 2 < total:
    sys.exit(f"取得成功が半分未満({ok}/{total})のため、ルールどおり生成を中止")
