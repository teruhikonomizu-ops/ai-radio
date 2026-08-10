"""
掛け合い台本の音声(mp3)とタイミング情報(*.segments.json)から、
ソラ・ピコの立ち絵(口パク)+字幕付きのYouTube用動画(MP4)を生成する。

使い方:
  python scripts/create_video.py <audio_path> <script_path> <artwork_path> <output_mp4_path> <show_type>

<script_path>は未使用(旧インターフェース互換のため引数だけ残している)。
実際のセリフ・タイミングは <audio_path> と同じ名前の *.segments.json
(tts_voicevox.py が出力)から読む。
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
FPS = 5                 # 口パクの切り替え頻度を兼ねる動画フレームレート
MOUTH_TOGGLE_SEC = 0.22  # しゃべっている間、口の開閉を切り替える間隔

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "characters"

SHOW_THEME = {
    "news": {"accent": (37, 99, 235), "label": "【AIデイリーニュース】"},
    "tech": {"accent": (124, 58, 237), "label": "【世界のAIニュース】"},
}

CHAR_INFO = {
    "ソラ": {"file_prefix": "sora", "color": (147, 197, 253)},
    "ピコ": {"file_prefix": "pico", "color": (253, 186, 116)},
}


def get_audio_duration(audio_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return float(res.stdout.strip())
    return 600.0


def get_japanese_font(size, bold=False):
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap_text(text, max_chars=32):
    lines, current = [], ""
    for ch in text:
        current += ch
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def load_character_images(char_height=560):
    images = {}
    for name, info in CHAR_INFO.items():
        variants = {}
        for state in ("open", "closed"):
            p = ASSETS_DIR / f"{info['file_prefix']}_{state}.png"
            im = Image.open(p).convert("RGBA")
            ratio = char_height / im.height
            im = im.resize((int(im.width * ratio), char_height), Image.LANCZOS)
            variants[state] = im
        images[name] = variants
    return images


def build_base_background(show_type, date_str):
    theme = SHOW_THEME[show_type]
    accent = theme["accent"]
    bg_top = (15, 23, 42)
    bg_bottom = (30, 27, 55) if show_type == "tech" else (17, 34, 64)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_top)
    px = img.load()
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(bg_top[0] + (bg_bottom[0] - bg_top[0]) * t)
        g = int(bg_top[1] + (bg_bottom[1] - bg_top[1]) * t)
        b = int(bg_top[2] + (bg_bottom[2] - bg_top[2]) * t)
        for x in range(0, WIDTH, 4):  # 4px間引きで塗って高速化
            for dx in range(4):
                if x + dx < WIDTH:
                    px[x + dx, y] = (r, g, b)

    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, 14], fill=accent)

    font_header = get_japanese_font(42, bold=True)
    draw.text((70, 44), f"{theme['label']}  {date_str}", font=font_header, fill=(255, 255, 255))

    # 字幕パネルの土台(半透明帯)をあらかじめ描いておく
    draw.rectangle([0, HEIGHT - 260, WIDTH, HEIGHT], fill=(10, 12, 22))
    draw.rectangle([0, HEIGHT - 260, WIDTH, HEIGHT - 256], fill=accent)

    return img


def draw_frame(base_img, char_images, active_speaker, mouth_open, caption_text, fonts):
    frame = base_img.copy()
    draw = ImageDraw.Draw(frame)

    positions = {"ソラ": (WIDTH // 4, HEIGHT - 300), "ピコ": (WIDTH * 3 // 4, HEIGHT - 300)}
    for name, (cx, cy) in positions.items():
        speaking = (name == active_speaker)
        state = "open" if (speaking and mouth_open) else "closed"
        im = char_images[name][state]
        scale = 1.0 if speaking else 0.88
        w, h = int(im.width * scale), int(im.height * scale)
        disp = im.resize((w, h), Image.LANCZOS) if scale != 1.0 else im
        if not speaking:
            # 話していない方は少し暗くして目立たなくする(透明部分は保ったままRGBだけ暗くする)
            r, g, b, a = disp.split()
            rgb = Image.merge("RGB", (r, g, b))
            rgb = Image.eval(rgb, lambda v: int(v * 0.55))
            disp = Image.merge("RGBA", (*rgb.split(), a))
        x, y = cx - w // 2, cy - h
        frame.paste(disp, (x, y), disp)

        name_font = fonts["name"]
        color = CHAR_INFO[name]["color"] if speaking else (110, 118, 138)
        tw = draw.textlength(name, font=name_font)
        draw.text((cx - tw / 2, cy + 14), name, font=name_font, fill=color)

    if caption_text:
        lines = wrap_text(caption_text, max_chars=34)[:2]
        y = HEIGHT - 210
        for line in lines:
            tw = draw.textlength(line, font=fonts["caption"])
            draw.text(((WIDTH - tw) / 2, y), line, font=fonts["caption"], fill=(255, 255, 255))
            y += 60

    return frame


def render_video(audio_path, segments_path, output_mp4_path, show_type):
    duration = get_audio_duration(audio_path)
    segments = json.loads(Path(segments_path).read_text(encoding="utf-8")) if Path(segments_path).exists() else []

    date_match = None
    import re
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(audio_path))
    date_str = m.group(0) if m else ""

    char_images = load_character_images()
    base_img = build_base_background(show_type, date_str)
    fonts = {
        "name": get_japanese_font(30, bold=True),
        "caption": get_japanese_font(38),
    }

    total_frames = int(duration * FPS) + 1
    print(f"[INFO] フレーム生成中 (全 {total_frames} フレーム, {FPS}fps, {duration/60:.1f}分)...", flush=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_mp4_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    seg_idx = 0
    for fi in range(total_frames):
        t = fi / FPS
        while seg_idx < len(segments) - 1 and t >= segments[seg_idx]["end"]:
            seg_idx += 1
        seg = segments[seg_idx] if segments and segments[seg_idx]["start"] <= t < segments[seg_idx]["end"] else None
        active_speaker = seg["speaker"] if seg else None
        caption = seg["text"] if seg else ""
        mouth_open = int(t / MOUTH_TOGGLE_SEC) % 2 == 0

        frame = draw_frame(base_img, char_images, active_speaker, mouth_open, caption, fonts)
        proc.stdin.write(frame.convert("RGB").tobytes())

        if fi % (FPS * 30) == 0:
            print(f"  {fi}/{total_frames} フレーム", flush=True)

    proc.stdin.close()
    ret = proc.wait()
    if ret != 0:
        print("[ERROR] ffmpegの終了コードが異常")
        sys.exit(1)
    print(f"[OK] 動画生成完了: {output_mp4_path}")


def main():
    if len(sys.argv) < 5:
        print("Usage: python create_video.py <audio_path> <script_path> <artwork_path> <output_mp4_path> [show_type]")
        sys.exit(1)

    audio_path = sys.argv[1]
    output_mp4_path = sys.argv[4]
    show_type = sys.argv[5] if len(sys.argv) > 5 else "news"
    segments_path = str(Path(audio_path).with_suffix(".segments.json"))

    if not os.path.exists(audio_path):
        print(f"[ERROR] 音声ファイルが見つかりません: {audio_path}")
        sys.exit(1)

    render_video(audio_path, segments_path, output_mp4_path, show_type)


if __name__ == "__main__":
    main()
