# -*- coding: utf-8 -*-
"""エピソードの meta.json(フィード生成用メタ情報)を作る。
使い方: python3 write_meta.py <show> <YYYY-MM-DD> <mp3パス> <概要欄パス> <meta.jsonの出力先>
mp3の公開URLは、GitHub Releases のタグ <show>-<date>・アセット名 <show>-<date>.mp3 の規約から組み立てる。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

show, date, mp3_path, desc_path, out_path = sys.argv[1:6]
mp3 = Path(mp3_path)
desc = Path(desc_path).read_text(encoding="utf-8").strip()
title = desc.splitlines()[0].strip()

dur = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)]).strip())

repo = os.environ.get("GITHUB_REPOSITORY", "teruhikonomizu-ops/ai-radio")
url = f"https://github.com/{repo}/releases/download/{show}-{date}/{show}-{date}.mp3"

meta = {
    "show": show,
    "date": date,
    "title": title,
    "description": desc,
    "duration_sec": round(dur),
    "size_bytes": mp3.stat().st_size,
    "url": url,
}
Path(out_path).write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"meta.json: {title} / {dur/60:.1f}分 / {mp3.stat().st_size/1e6:.1f}MB")
