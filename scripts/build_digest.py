# -*- coding: utf-8 -*-
"""2番組共通のダイジェスト組み立て。collect_news.py / collect_ai_news.py から呼ばれる。

やること:
  1. 主力ソースを取得し、直近◯時間のものだけ選ぶ(古い記事を今日の話として読ませない)
  2. 放送済み台帳と照合し【新規】と【既報】に振り分ける
  3. 【新規】が目標本数に届かなければ、時間窓を広げ → 予備ソースを足し → さらに広げる
     (「ニュースが無いから同じ話を繰り返す/水増しする」を防ぎ、10分ぶんの素材を確保する)
  4. 更新が止まっているフィードを見つけて警告として書き出す
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import broadcast_log
import feeds


def _count(groups):
    return sum(len(v) for _, v in groups)


def _split(groups, match):
    """【新規】と【既報】に振り分ける。既報には「いつ・どのトピックで放送したか」を添える。"""
    fresh, old = [], []
    for name, items in groups:
        f, o = [], []
        for it in items:
            hit = match(it["title"] + " " + it["desc"])
            (o if hit else f).append(dict(it, seen=hit))
        if f:
            fresh.append((name, f))
        if o:
            old.append((name, o))
    return fresh, old


def run(show_label, main_sources, backup_sources, out_path, *,
        hours=36, min_new=18, per_source=12, max_total=70, desc_len=140,
        stale_days=3, logs=()):
    now = feeds.now_jst()
    print(f"[{show_label}] 収集開始 {now.strftime('%Y-%m-%d %H:%M')} / 鮮度 直近{hours}時間 / 新規目標 {min_new}本")

    # --- 放送済み台帳(自番組＋もう一方の番組)を読み込んで照合器を作る ---
    entries = []
    for p in logs:
        e = broadcast_log.load(p)
        print(f"  台帳 {p}: {len(e)}件(照合対象は直近{broadcast_log.MATCH_DAYS}日)")
        entries += e
    match = broadcast_log.matcher(entries, today=now.date())

    # --- 主力ソースを1回だけ取得。窓の広げ直しはメモリ上でやる ---
    all_main, stats = feeds.fetch_all(main_sources)
    print(f"  主力ソース取得 {stats['ok']}/{stats['total']}")
    for n in stats["ng"]:
        print(f"  ::取得失敗:: {n}")

    plan = [(hours, False, False), (hours * 2, False, False),
            (hours * 2, True, False), (hours * 4, True, False), (hours * 4, True, True)]
    all_backup = None
    fresh = old = []
    used_hours, used_backup, used_undated = hours, False, False
    for i, (h, use_backup, keep_undated) in enumerate(plan):
        if use_backup and all_backup is None:
            if not backup_sources:
                continue
            all_backup, bstats = feeds.fetch_all(backup_sources)
            stats["ng"] += bstats["ng"]
            stats["newest"].update(bstats["newest"])
            stats["ok"] += bstats["ok"]
            stats["total"] += bstats["total"]
            print(f"  予備ソース取得 {bstats['ok']}/{bstats['total']}")
        seen = set()
        groups = feeds.select(all_main, h, per_source, seen, keep_undated)
        if use_backup and all_backup:
            groups += feeds.select(all_backup, h, per_source, seen, keep_undated)
        fresh, old = _split(groups, match)
        used_hours, used_backup, used_undated = h, use_backup, keep_undated
        n = _count(fresh)
        print(f"  段階{i+1}: 直近{h}時間{'＋予備' if use_backup else ''}"
              f"{'＋日付不明も採用' if keep_undated else ''} → 新規{n}本 / 既報{_count(old)}本")
        if n >= min_new:
            break

    notes = []
    if used_hours != hours:
        notes.append(f"新規が{min_new}本に届かなかったため、鮮度の窓を直近{used_hours}時間まで広げた")
    if used_backup:
        notes.append("それでも足りないため、予備ソースを追加して集めた")
    if used_undated:
        notes.append("さらに足りないため、配信日が読み取れない記事も素材に含めた(古い可能性あり・扱いは慎重に)")
    if _count(fresh) < min_new:
        notes.append(f"⚠それでも新規は{_count(fresh)}本にとどまった。"
                     "本数が少ないぶん1本あたりを掘り下げて、規定の長さを確保すること(同じ話の繰り返しで水増ししない)")

    # --- 総量を上限で切る(トークン節約。各ソースから均等に減らす) ---
    while _count(fresh) > max_total:
        biggest = max(range(len(fresh)), key=lambda i: len(fresh[i][1]))
        fresh[biggest][1].pop()
        fresh = [(n, v) for n, v in fresh if v]

    stale = feeds.check_stale(stats["newest"], stale_days)

    # --- 書き出し ---
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        p = lambda s="": print(s, file=f)
        p(f"# {show_label}ダイジェスト {now.strftime('%Y-%m-%d %H:%M')}(日本時間)")
        p(f"# 各行の [今日][昨日][N日前] は記事の配信日時。今日と昨日のものを優先して扱うこと。")
        p(f"# 「新規」= まだ放送していない話題 / 「既報」= 直近{broadcast_log.MATCH_DAYS}日の放送で扱い済み")
        p()
        p("# ============ 新規（ここから選んで台本を作る） ============")
        for name, items in fresh:
            p(f"\n## {name}")
            for it in items:
                line = f"- [{it['label']}] {it['title']}"
                if it["desc"]:
                    line += f" — {it['desc'][:desc_len]}"
                p(line)
        if old:
            p()
            p("# ============ 既報（原則スキップ。新しい展開があるときだけ続報として短く） ============")
            for name, items in old:
                p(f"\n## {name}(既報)")
                for it in items:
                    d, topic = it["seen"]
                    line = f"- [{it['label']}](既報 {d}「{topic}」) {it['title']}"
                    if it["desc"]:
                        line += f" — {it['desc'][:desc_len]}"
                    p(line)
        p()
        p("## 収集メモ")
        p(f"- 新規 {_count(fresh)}本 / 既報 {_count(old)}本 / 鮮度の窓 直近{used_hours}時間")
        for n in dict.fromkeys(notes):
            p(f"- {n}")
        if stale:
            p(f"- ⚠更新停止の疑いがあるソース({stale_days}日以上新着なし):")
            for s in stale:
                p(f"  - {s}")
        if stats["ng"]:
            p("- 取得失敗:")
            for n in stats["ng"]:
                p(f"  - {n}")
        p(f"\n(取得成功 {stats['ok']}/{stats['total']} ソース)")
        p(f"(新規 {_count(fresh)}本 / 既報 {_count(old)}本 / 更新停止疑い {len(stale)}件)")

    print(f"  → {out} に書き出した(新規{_count(fresh)}本 / 既報{_count(old)}本)")
    if stale:
        for s in stale:
            print(f"  ::warning::更新停止の疑い {s}")
    return _count(fresh), _count(old), stale
