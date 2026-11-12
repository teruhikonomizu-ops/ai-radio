#!/usr/bin/env python3
"""Claude Code を「公開から N 日たった版だけ」で入れる（部品の乗っ取り対策・2026-11-08 のみさん承認）。

2026-11-13 改修。それまでは `npm install -g @anthropic-ai/claude-code --min-release-age=3` の1行だった。

落ちた原因（2026-11-13 朝の放送）:
  npm はこの待ち期間を「本体」と「実行ファイルの部品（@anthropic-ai/claude-code-linux-x64 など）」で
  別々に判定する。部品は本体の約4分後に公開されるので、版が出てちょうど N 日後の約4分間だけ
  「本体は入るが、実行ファイルの部品は若すぎて入らない」状態になる。部品は「無くてもよい物」の扱い
  なので npm はエラーにせず、claude は "native binary not installed" で動かない。
  （2.1.321: 本体 11/09 19:02:47Z・部品 19:06:45Z → 11/12 19:05Z のインストールが命中）

直し方:
  1. 本体と実行ファイルの部品の「両方」が N 日たった版のうち、いちばん新しい版を自分で選ぶ
  2. その版を名指しして入れる（npm 側の待ち期間 --min-release-age も付けたまま＝二重の守り）
  3. 入れた後に `claude --version` が通ることまで確かめる。通らなければ1つ古い版で入れ直す
  4. どの版でも動かなければ、この手順を赤にして止める（鍵を持つ次の手順まで行かせない）

使い方:
  python3 scripts/install_claude_code.py --days 3
  python3 scripts/install_claude_code.py --days 3 --dry-run                      # 選ぶ版を表示するだけ
  python3 scripts/install_claude_code.py --days 3 --dry-run --now 2026-11-12T19:05:00Z   # 過去の時刻で試す
"""
import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

PKG = "@anthropic-ai/claude-code"
MARGIN_SEC = 600   # 境目ぎりぎりを避ける余裕（npm 側の判定と数秒ずれても食い違わないように）
MAX_TRY = 3        # 新しい順に何版まで試すか

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    print(msg, flush=True)


def npm_exe():
    exe = shutil.which("npm")
    if not exe:
        raise RuntimeError("npm が見つからない")
    return exe


def native_pkg():
    """このマシン用の「実行ファイルの部品」の名前。分からなければ None。"""
    osname = {"linux": "linux", "darwin": "darwin", "win32": "win32"}.get(sys.platform)
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not osname or not arch:
        return None
    return f"{PKG}-{osname}-{arch}"


def npm_view(pkg):
    """公開時刻・版の一覧・latest の印を npm の公開情報から取る。"""
    out = subprocess.run(
        [npm_exe(), "view", pkg, "time", "versions", "dist-tags", "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"npm view {pkg} が失敗: {out.stderr.strip()[-300:]}")
    return json.loads(out.stdout)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def vkey(v):
    return tuple(int(x) for x in v.split("."))


def pick_versions(days, now):
    """本体と実行ファイルの部品の両方が days 日たった版を、新しい順に返す。"""
    npkg = native_pkg()
    if not npkg:
        raise RuntimeError(f"このマシンの種類が分からない（{sys.platform} / {platform.machine()}）")
    main, native = npm_view(PKG), npm_view(npkg)
    cutoff = now - timedelta(days=days, seconds=MARGIN_SEC)
    latest = main.get("dist-tags", {}).get("latest")
    main_versions, native_versions = set(main.get("versions", [])), set(native.get("versions", []))
    picked = []
    for v, t in main.get("time", {}).items():
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            continue                      # created / modified ・試験版は見ない
        if v not in main_versions or v not in native_versions:
            continue                      # 取り下げられた版・部品がまだ無い版
        if latest and vkey(v) > vkey(latest):
            continue                      # latest より先の版（next だけの版）は入れない
        nt = native.get("time", {}).get(v)
        if not nt:
            continue
        if parse_time(t) <= cutoff and parse_time(nt) <= cutoff:
            picked.append(v)
    picked.sort(key=vkey, reverse=True)
    log(f"基準: {now:%Y-%m-%d %H:%M:%S}Z の {days} 日前（余裕 {MARGIN_SEC // 60} 分）＝ {cutoff:%Y-%m-%d %H:%M:%S}Z より前に公開された版")
    log(f"実行ファイルの部品: {npkg} ／ latest: {latest} ／ 条件を満たす版（新しい順）: {', '.join(picked[:MAX_TRY]) or 'なし'}")
    return picked[:MAX_TRY]


def install(spec, days):
    """入れて、動くことまで確かめる。動けば版の文字列、だめなら None。"""
    log(f"--- 入れる: {spec}")
    r = subprocess.run([npm_exe(), "install", "-g", spec, f"--min-release-age={days}"])
    if r.returncode != 0:
        log(f"npm install が失敗（終了コード {r.returncode}）")
        return None
    exe = shutil.which("claude")
    if not exe:
        log("claude が見つからない（PATH）")
        return None
    v = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", timeout=120)
    text = (v.stdout + v.stderr).strip()
    if v.returncode != 0:
        log("claude --version が失敗（実行ファイルの部品が入っていない等）:")
        log(text[-600:])
        return None
    log(f"claude --version: {text}")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="公開から何日たった版だけを入れるか")
    ap.add_argument("--dry-run", action="store_true", help="選ぶ版を表示するだけ（入れない）")
    ap.add_argument("--now", help="基準時刻（ISO・UTC）。試し用。--dry-run の時だけ使える")
    a = ap.parse_args()
    if a.now and not a.dry_run:
        sys.exit("--now は --dry-run と一緒にだけ使える（本番で基準時刻をずらすと待ち期間が崩れる）")
    now = parse_time(a.now) if a.now else datetime.now(timezone.utc)

    # npm 自身が待ち期間を知っているか（知らなくても、下で版を自分で選ぶので待ち期間は守られる）
    cfg = subprocess.run([npm_exe(), "config", "ls", "-l"], capture_output=True, text=True, encoding="utf-8")
    if "min-release-age" not in cfg.stdout:
        log("::warning::このnpmは待ち期間（min-release-age）に未対応。版は自前で選ぶので待ち期間は守られるが、ワークフローの見直しが必要です")

    try:
        versions = pick_versions(a.days, now)
    except Exception as e:  # 公開情報が取れない時は、従来の入れ方に落とす（下で動作まで確かめる）
        log(f"::warning::版を自前で選べなかった（{e}）。npm の待ち期間だけで入れる")
        versions = []

    if a.dry_run:
        log(f"（試し）入れる版: {versions[0] if versions else 'npm に任せる'}")
        return

    specs = [f"{PKG}@{v}" for v in versions] or [PKG]
    for i, spec in enumerate(specs):
        if install(spec, a.days):
            if i > 0:
                log(f"::warning::いちばん新しい候補では動かず、{spec} に下げて入れた。ログを一度見てください")
            return
    log("::error::Claude Code を入れられなかった（どの版でも claude --version が通らない）。scripts/install_claude_code.py のログを見てください")
    sys.exit(1)


if __name__ == "__main__":
    main()
