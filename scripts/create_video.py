"""
ソロ台本の音声(mp3)とタイミング情報(*.segments.json)から、
番組専属キャラの立ち絵(口パク)+大きな字幕付きのYouTube用動画(MP4)を生成する。

使い方:
  python scripts/create_video.py <audio_path> <script_path> <artwork_path> <output_mp4_path> <show_type>

<script_path>・<artwork_path>は未使用(旧インターフェース互換のため引数だけ残している)。
実際のセリフ・タイミングは <audio_path> と同じ名前の *.segments.json
(tts_aivis.py が出力)から読む。
"""
import sys
import os
import re
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
FPS = 5                 # 口パクの切り替え頻度を兼ねる動画フレームレート
MOUTH_TOGGLE_SEC = 0.22  # しゃべっている間、口の開閉を切り替える間隔

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "characters"

SHOW_THEME = {
    "news": {"accent": (37, 99, 235), "label": "【AIデイリーニュース】", "character": "ソラ"},
    "tech": {"accent": (124, 58, 237), "label": "【世界のAIニュース】", "character": "ピコ"},
}

CHAR_FILE_PREFIX = {"ソラ": "sora", "ピコ": "pico"}


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


def wrap_text(text, max_chars=15):
    lines, current = [], ""
    for ch in text:
        current += ch
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def load_character_image(character, char_height=900):
    variants = {}
    prefix = CHAR_FILE_PREFIX[character]
    for state in ("open", "closed"):
        p = ASSETS_DIR / f"{prefix}_{state}.png"
        im = Image.open(p).convert("RGBA")
        ratio = char_height / im.height
        im = im.resize((int(im.width * ratio), char_height), Image.LANCZOS)
        variants[state] = im
    return variants


def build_base_background(show_type, date_str):
    theme = SHOW_THEME[show_type]
    accent = theme["accent"]
    bg_left = (15, 23, 42)
    bg_right = (30, 27, 55) if show_type == "tech" else (17, 34, 64)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_left)
    px = img.load()
    for x in range(WIDTH):
        t = x / WIDTH
        r = int(bg_left[0] + (bg_right[0] - bg_left[0]) * t)
        g = int(bg_left[1] + (bg_right[1] - bg_left[1]) * t)
        b = int(bg_left[2] + (bg_right[2] - bg_left[2]) * t)
        for y in range(0, HEIGHT, 4):  # 4px間引きで塗って高速化
            for dy in range(4):
                if y + dy < HEIGHT:
                    px[x, y + dy] = (r, g, b)

    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, 14], fill=accent)

    font_header = get_japanese_font(40, bold=True)
    draw.text((60, 40), f"{theme['label']}  {date_str}", font=font_header, fill=(255, 255, 255))

    # キャラと字幕を分ける縦のアクセントライン
    draw.rectangle([720, 0, 726, HEIGHT], fill=accent)

    return img


def draw_frame(base_img, char_variants, mouth_open, caption_text, fonts, accent):
    frame = base_img.copy()
    draw = ImageDraw.Draw(frame)

    state = "open" if mouth_open else "closed"
    im = char_variants[state]
    cx, cy = 360, HEIGHT - 40
    x, y = cx - im.width // 2, cy - im.height
    frame.paste(im, (x, y), im)

    if caption_text:
        lines = wrap_text(caption_text, max_chars=15)[:6]
        line_h = 78
        total_h = len(lines) * line_h
        y = max(140, (HEIGHT - total_h) // 2)
        x = 800
        for line in lines:
            draw.text((x, y), line, font=fonts["caption"], fill=(255, 255, 255))
            y += line_h

    return frame


def render_video(audio_path, segments_path, output_mp4_path, show_type):
    duration = get_audio_duration(audio_path)
    segments = json.loads(Path(segments_path).read_text(encoding="utf-8")) if Path(segments_path).exists() else []

    m = re.search(r"\d{4}-\d{2}-\d{2}", str(audio_path))
    date_str = m.group(0) if m else ""

    theme = SHOW_THEME[show_type]
    character = theme["character"]
    char_variants = load_character_image(character)
    base_img = build_base_background(show_type, date_str)
    fonts = {"caption": get_japanese_font(56, bold=True)}

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
        caption = seg["text"] if seg else ""
        mouth_open = bool(seg) and (int(t / MOUTH_TOGGLE_SEC) % 2 == 0)

        frame = draw_frame(base_img, char_variants, mouth_open, caption, fonts, theme["accent"])
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
