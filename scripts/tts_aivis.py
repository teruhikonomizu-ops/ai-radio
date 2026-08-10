# -*- coding: utf-8 -*-
"""掛け合い台本(ソラ/ピコ) → AivisSpeech Engine(無料・OSS)で2話者音声合成 → mp3/wav。
使い方:
  python tts_aivis.py 台本.txt 出力.mp3 \
      [--sora-speaker 497929760] [--pico-speaker 1878365376] \
      [--speed 1.0] [--sora-pitch 0.0] [--pico-pitch 0.0] \
      [--sora-intonation 1.0] [--pico-intonation 1.0]
前提: AivisSpeech Engine が http://127.0.0.1:10101 で起動していること(公式Dockerイメージ)。
話者はVOICEVOX/AivisSpeech共通のキャラ名でも、styleIdの数字でも指定できる。
台本の書き方:
  ・1行 = 1人のセリフ。行頭に「ソラ: 」または「ピコ: 」(半角コロン)
  ・空行 = 話者交代・段落の区切り(0.7秒の間が入る)
  ・「#」で始まる行はコメント(読まれない)
外部ライブラリ不要(標準ライブラリ+ffmpeg)。
"""
import sys
import io
import json
import re
import wave
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://127.0.0.1:10101"
PARA_PAUSE_SEC = 0.7
SENT_PAUSE_SEC = 0.0
SPEAKERS = ("ソラ", "ピコ")


def api(path: str, method="GET", body=None, timeout=180):
    req = urllib.request.Request(BASE + path, method=method,
                                  data=json.dumps(body).encode() if body is not None else b"",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        data = r.read()
        return json.loads(data) if "json" in ct else data


def resolve_speaker(name_or_id: str):
    """キャラ名(例:「四国めたん」)またはstyleIdの数字を、実際のstyleIdに解決する"""
    speakers = api("/speakers")
    styles = [(sp["name"], st["name"], st["id"]) for sp in speakers for st in sp["styles"]]
    if name_or_id.isdigit():
        sid = int(name_or_id)
        for name, sname, s in styles:
            if s == sid:
                return sid, f"{name}({sname})"
        raise SystemExit(f"styleId {sid} が見つからない。利用可能: {styles}")
    for name, sname, s in styles:
        if name == name_or_id and ("ノーマル" in sname or "通常" in sname or "Normal" in sname):
            return s, f"{name}({sname})"
    for name, sname, s in styles:
        if name == name_or_id:
            return s, f"{name}({sname})"
    raise SystemExit(f"キャラ名 '{name_or_id}' が見つからない。利用可能な名前: {sorted(set(n for n, _, _ in styles))}")


def split_sentences(paragraph: str):
    parts = re.split(r"(?<=[。！？!?])", paragraph)
    return [p.strip() for p in parts if p.strip()]


def synthesize(text: str, speaker: int, speed: float, pitch: float, intona: float) -> bytes:
    q = api(f"/audio_query?speaker={speaker}&text={urllib.parse.quote(text)}", method="POST")
    q["speedScale"] = speed
    q["pitchScale"] = pitch
    q["intonationScale"] = intona
    return api(f"/synthesis?speaker={speaker}", method="POST", body=q)


def parse_script(text: str):
    """行を (speaker, text) のリストに変換。空行は None を挟んで段落区切りを表す"""
    items = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if items and items[-1] is not None:
                items.append(None)
            continue
        if line.startswith("#"):
            continue
        m = re.match(r"^(ソラ|ピコ):\s*(.+)$", line)
        if not m:
            raise SystemExit(f"話者タグが無い行が見つかった(ソラ:/ピコ: で始まっていない): {line!r}")
        items.append((m.group(1), m.group(2)))
    while items and items[-1] is None:
        items.pop()
    return items


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {}
    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a.startswith("--"):
            opts[a] = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    if len(args) < 2:
        raise SystemExit(__doc__)
    src, dst = Path(args[0]), Path(args[1])

    speed = float(opts.get("--speed", "1.0"))
    sent_pause = float(opts.get("--sentpause", str(SENT_PAUSE_SEC)))
    para_pause = float(opts.get("--parapause", str(PARA_PAUSE_SEC)))

    version = api("/version")
    speaker_ids = {}
    for name, opt_key, default in (
        ("ソラ", "--sora-speaker", "497929760"),
        ("ピコ", "--pico-speaker", "1878365376"),
    ):
        sid, label = resolve_speaker(opts.get(opt_key, default))
        pitch = float(opts.get(f"--{'sora' if name == 'ソラ' else 'pico'}-pitch", "0.0"))
        intona = float(opts.get(f"--{'sora' if name == 'ソラ' else 'pico'}-intonation", "1.0"))
        speaker_ids[name] = {"id": sid, "label": label, "pitch": pitch, "intonation": intona}
        print(f"{name}: {label} (styleId={sid}) / pitch {pitch} / 抑揚 {intona}")
    print(f"engine {version} / 速度 {speed}")

    text = src.read_text(encoding="utf-8")
    items = parse_script(text)
    total = sum(1 for it in items if it is not None)
    print(f"セリフ行 {total}")

    frames = bytearray()
    params = None
    done = 0
    segments = []  # 動画側の字幕・口パク同期用: 1文=1セグメント(行より細かく刻んで字幕のズレを防ぐ)

    def silence(sec):
        n = int(params.framerate * sec)
        return b"\x00" * (n * params.sampwidth * params.nchannels)

    def cur_time():
        if params is None:
            return 0.0
        return len(frames) / (params.framerate * params.sampwidth * params.nchannels)

    pending_para_pause = False
    for item in items:
        if item is None:
            pending_para_pause = True
            continue
        speaker, line_text = item
        spk = speaker_ids[speaker]
        sentences = split_sentences(line_text)
        for si, s in enumerate(sentences):
            sent_start = cur_time()
            wav_bytes = synthesize(s, spk["id"], speed, spk["pitch"], spk["intonation"])
            with wave.open(io.BytesIO(wav_bytes)) as w:
                if params is None:
                    params = w.getparams()
                    sent_start = cur_time()
                frames += w.readframes(w.getnframes())
            segments.append({"speaker": speaker, "text": s,
                              "start": round(sent_start, 3), "end": round(cur_time(), 3)})
            if sent_pause > 0 and si < len(sentences) - 1:
                frames += silence(sent_pause)
        done += 1
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total} 行 合成済み")
        if pending_para_pause:
            frames += silence(para_pause)
            pending_para_pause = False

    dur = len(frames) / (params.framerate * params.sampwidth * params.nchannels)
    tmp_wav = Path(tempfile.gettempdir()) / "radio_tmp.wav"
    with wave.open(str(tmp_wav), "wb") as w:
        w.setparams(params)
        w.writeframes(bytes(frames))

    if dst.suffix.lower() == ".wav":
        shutil.copy(tmp_wav, dst)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_wav),
                        "-b:a", "128k", str(dst)], check=True)
    tmp_wav.unlink(missing_ok=True)

    segments_path = dst.with_suffix(".segments.json")
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=1), encoding="utf-8")

    mb = dst.stat().st_size / 1024 / 1024
    print(f"完成: {dst} ({dur/60:.1f}分, {mb:.1f}MB) / タイミング: {segments_path}")


if __name__ == "__main__":
    main()
