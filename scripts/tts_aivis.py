# -*- coding: utf-8 -*-
"""ニュースラジオ用: 台本テキスト → AivisSpeech Engine(ローカル・無料)で音声合成 → mp3/wav。
使い方:
  python tts_aivis.py 台本.txt 出力.mp3 [--speaker <styleId>] [--speed 1.0]
前提: AivisSpeech Engine が http://127.0.0.1:10101 で起動していること。
  起動: %USERPROFILE%\\aivisspeech 配下の run.exe
台本の書き方:
  ・空行 = 段落の区切り(0.7秒の間が入る)
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
PARA_PAUSE_SEC = 0.7   # 段落間の間(--parapause で変更可)
SENT_PAUSE_SEC = 0.0   # 文間の間(--sentpause で変更可)

def api(path: str, method="GET", body=None, timeout=180):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else b"",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        data = r.read()
        return json.loads(data) if "json" in ct else data

def pick_speaker(requested=None):
    speakers = api("/speakers")
    styles = [(sp["name"], st["name"], st["id"]) for sp in speakers for st in sp["styles"]]
    if requested is not None:
        for name, sname, sid in styles:
            if sid == requested:
                return sid, f"{name}({sname})"
        raise SystemExit(f"styleId {requested} が見つからない。利用可能: {styles}")
    # 指定なしはノーマル系を優先して最初のスタイル
    for name, sname, sid in styles:
        if "ノーマル" in sname or "通常" in sname or "Normal" in sname:
            return sid, f"{name}({sname})"
    name, sname, sid = styles[0]
    return sid, f"{name}({sname})"

def split_sentences(paragraph: str):
    # 文単位に分割(長すぎる合成要求を避け、進捗も見えるように)
    parts = re.split(r"(?<=[。！？!?])", paragraph)
    return [p.strip() for p in parts if p.strip()]

def synthesize(text: str, speaker: int, speed: float, pitch=None, intona=None) -> bytes:
    q = api(f"/audio_query?speaker={speaker}&text={urllib.parse.quote(text)}", method="POST")
    q["speedScale"] = speed
    if pitch is not None:      # 声の高さ(下げると落ち着いた大人っぽい低め)
        q["pitchScale"] = pitch
    if intona is not None:     # 抑揚(下げると平坦・淡々。アナウンサー調)
        q["intonationScale"] = intona
    return api(f"/synthesis?speaker={speaker}", method="POST", body=q)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    for name in ("--speaker", "--speed", "--sentpause", "--parapause", "--pitch", "--intonation"):
        if name in sys.argv:
            opts[name] = sys.argv[sys.argv.index(name) + 1]
    if len(args) < 2:
        raise SystemExit(__doc__)
    src, dst = Path(args[0]), Path(args[1])
    speed = float(opts.get("--speed", "1.0"))
    sent_pause = float(opts.get("--sentpause", SENT_PAUSE_SEC))
    para_pause = float(opts.get("--parapause", PARA_PAUSE_SEC))
    pitch = float(opts["--pitch"]) if "--pitch" in opts else None
    intona = float(opts["--intonation"]) if "--intonation" in opts else None
    requested = int(opts["--speaker"]) if "--speaker" in opts else None

    version = api("/version")
    speaker, spk_name = pick_speaker(requested)
    print(f"engine {version} / 話者: {spk_name} (styleId={speaker}) / 速度 {speed} / pitch {pitch} / 抑揚 {intona}")

    text = src.read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text)
                  if p.strip() and not all(l.startswith("#") for l in p.strip().splitlines())]
    sentences_by_para = []
    for p in paragraphs:
        lines = [l for l in p.splitlines() if not l.startswith("#")]
        sentences_by_para.append(split_sentences(" ".join(lines)))

    total = sum(len(s) for s in sentences_by_para)
    print(f"段落 {len(sentences_by_para)} / 文 {total}")

    frames = bytearray()
    params = None
    done = 0

    def silence(sec):
        n = int(params.framerate * sec)
        return b"\x00" * (n * params.sampwidth * params.nchannels)

    for pi, sentences in enumerate(sentences_by_para):
        for si, s in enumerate(sentences):
            wav_bytes = synthesize(s, speaker, speed, pitch, intona)
            with wave.open(io.BytesIO(wav_bytes)) as w:
                if params is None:
                    params = w.getparams()
                frames += w.readframes(w.getnframes())
            if sent_pause > 0 and si < len(sentences) - 1:  # 文間ポーズ
                frames += silence(sent_pause)
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  {done}/{total} 文 合成済み")
        if pi < len(sentences_by_para) - 1:  # 段落間ポーズ
            frames += silence(para_pause)

    dur = len(frames) / (params.framerate * params.sampwidth * params.nchannels)
    tmp_wav = Path(tempfile.gettempdir()) / "newsradio_tmp.wav"
    with wave.open(str(tmp_wav), "wb") as w:
        w.setparams(params)
        w.writeframes(bytes(frames))

    if dst.suffix.lower() == ".wav":
        shutil.copy(tmp_wav, dst)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_wav),
                        "-b:a", "128k", str(dst)], check=True)
    tmp_wav.unlink(missing_ok=True)
    mb = dst.stat().st_size / 1024 / 1024
    print(f"完成: {dst} ({dur/60:.1f}分, {mb:.1f}MB)")

if __name__ == "__main__":
    main()
