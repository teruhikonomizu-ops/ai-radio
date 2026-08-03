"""
台本(台本.txt)と音声(MP3)からトピックごとのスライド動画(MP4)を自動生成するスクリプト

使い方:
  python scripts/create_video.py <audio_path> <script_path> <artwork_path> <output_mp4_path> <show_type>
"""

import sys
import os
import re
import subprocess
from PIL import Image, ImageDraw, ImageFont

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return float(res.stdout.strip())
    return 600.0  # fallback 10 mins

def get_japanese_font(size):
    font_paths = [
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/yu-gothic.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

def wrap_text(text, max_chars=36):
    """テキストを画面幅に合わせて自然に折り返すヘルパー"""
    lines = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines

def chunk_sentences(sentences, max_chars_per_slide=140):
    """喋っている文章を溢れさせず複数スライドに分割するヘルパー"""
    chunks = []
    current_chunk = []
    current_len = 0
    for s in sentences:
        if current_len + len(s) > max_chars_per_slide and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [s]
            current_len = len(s)
        else:
            current_chunk.append(s)
            current_len += len(s)
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def parse_sections(script_path):
    if not os.path.exists(script_path):
        return []

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    raw_sections = []

    # パターン1: # ヘッダーで区切られている場合 (newsラジオ等)
    if "#" in content:
        raw_blocks = re.split(r'\n(?=#\s*)', content)
        for idx, block in enumerate(raw_blocks):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            
            header_line = lines[0]
            if header_line.startswith("#"):
                raw_title = re.sub(r'^[#\s─\-]+|[─\-\s]+$', '', header_line).strip()
                body_lines = lines[1:]
            else:
                raw_title = "番組紹介"
                body_lines = lines

            text_lines = [l for l in body_lines if not l.startswith("#")]
            full_text = " ".join(text_lines)
            if not full_text:
                continue

            if idx == 0 or "オープニング" in raw_title:
                title = "番組紹介"
            else:
                title = raw_title or "ニュース"

            sentences = [s.strip() for s in re.split(r'[。！？\n]', full_text) if s.strip()]
            raw_sections.append({"title": title, "sentences": sentences})

    # パターン2: ヘッダーがなく段落区切りの場合 (techラジオ等)
    if not raw_sections:
        raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        topic_counter = 1

        for idx, p in enumerate(raw_paragraphs):
            lines = [l for l in p.split("\n") if not l.startswith("#")]
            full_text = " ".join(lines)
            if not full_text:
                continue

            if idx == 0:
                title = "番組紹介"
            elif "ダイジェスト" in full_text or "見出し" in full_text:
                title = "本日の主なニュース"
            elif "一つ目" in full_text or "1つ目" in full_text:
                title = f"トピック {topic_counter}"
                topic_counter += 1
            elif "二つ目" in full_text or "2つ目" in full_text:
                title = f"トピック {topic_counter}"
                topic_counter += 1
            elif "三つ目" in full_text or "3つ目" in full_text:
                title = f"トピック {topic_counter}"
                topic_counter += 1
            elif "四つ目" in full_text or "4つ目" in full_text:
                title = f"トピック {topic_counter}"
                topic_counter += 1
            elif "五つ目" in full_text or "5つ目" in full_text:
                title = f"トピック {topic_counter}"
                topic_counter += 1
            elif "ここからは" in full_text or "そのほか" in full_text:
                title = "注目のAIニュース"
            elif "以上" in full_text or "おわり" in full_text:
                title = "エンディング"
            else:
                title = f"トピック {topic_counter}"
                topic_counter += 1

            sentences = [s.strip() for s in re.split(r'[。！？\n]', full_text) if s.strip()]
            raw_sections.append({"title": title, "sentences": sentences})

    # 喋っている全文章を漏れなくスライド化 (1スライドに入り切らない場合は同タイトルで複数スライドに分割)
    final_slides = []
    for sec in raw_sections:
        sentence_chunks = chunk_sentences(sec["sentences"], max_chars_per_slide=130)
        for chunk in sentence_chunks:
            chunk_text = " ".join(chunk)
            final_slides.append({
                "title": sec["title"],
                "bullets": chunk,
                "char_count": len(chunk_text)
            })

    if not final_slides:
        final_slides.append({
            "title": "番組紹介",
            "bullets": ["最新のニュースをお届けします"],
            "char_count": 100
        })

    return final_slides

def create_slide_image(output_path, show_type, section_title, bullets, date_str):
    width, height = 1920, 1080
    bg_color = (15, 23, 42)      # Slate 900
    panel_color = (30, 41, 59)   # Slate 800
    accent_color = (37, 99, 235) if show_type == "news" else (124, 58, 237) # Blue / Purple
    text_white = (248, 250, 252)
    text_muted = (148, 163, 184)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = get_japanese_font(44)
    font_section = get_japanese_font(56)
    font_bullet = get_japanese_font(34)
    font_footer = get_japanese_font(30)

    # 1. 上部アクセントバー
    draw.rectangle([0, 0, width, 16], fill=accent_color)

    # 2. 番組ヘッダー
    show_name = "【AIデイリーニュース】" if show_type == "news" else "【世界のAIニュース】"
    header_text = f"{show_name}  {date_str}"
    draw.text((80, 50), header_text, font=font_title, fill=accent_color)

    # 3. トピックタイトルカード
    icon_symbol = "🎙️" if section_title in ["番組紹介", "オープニング", "エンディング"] else "📌"
    draw.rectangle([80, 130, 1840, 230], fill=accent_color)
    draw.text((120, 150), f"{icon_symbol}  {section_title}", font=font_section, fill=text_white)

    # 4. 箇条書きコンテンツパネル（全文章を表示）
    panel_y_start = 260
    panel_y_end = 960
    draw.rectangle([80, panel_y_start, 1840, panel_y_end], fill=panel_color)

    y_offset = panel_y_start + 40
    line_spacing = 46

    for b in bullets:
        wrapped_lines = wrap_text(b, max_chars=38)
        for i, line_text in enumerate(wrapped_lines):
            if y_offset > panel_y_end - 50:
                break
            if i == 0:
                draw.text((120, y_offset), "・", font=font_bullet, fill=accent_color)
                draw.text((160, y_offset), line_text, font=font_bullet, fill=text_white)
            else:
                draw.text((160, y_offset), line_text, font=font_bullet, fill=text_white)
            y_offset += line_spacing
        y_offset += 20  # 箇条書き間隔
        if y_offset > panel_y_end - 50:
            break

    # 5. 下部フッター
    draw.text((80, 995), "※ AI音声による全自動デイリーニュース配信", font=font_footer, fill=text_muted)

    img.save(output_path)

def create_multi_slide_video(audio_path, script_path, artwork_path, output_mp4_path, show_type):
    if not os.path.exists(audio_path):
        print(f"[ERROR] 音声ファイルが見つかりません: {audio_path}")
        sys.exit(1)

    total_duration = get_audio_duration(audio_path)
    slides_data = parse_sections(script_path)

    if not slides_data or not os.path.exists(script_path):
        if not os.path.exists(artwork_path):
            print("[ERROR] アートワーク画像も見つかりません")
            sys.exit(1)
        print("[INFO] 台本がないため静止画動画を作成します")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", artwork_path, "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", output_mp4_path
        ]
        subprocess.run(cmd, check=True)
        return

    total_chars = sum(s["char_count"] for s in slides_data) or 1
    work_dir = os.path.dirname(os.path.abspath(output_mp4_path))
    slides_dir = os.path.join(work_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    date_match = re.search(r'\d{4}-\d{2}-\d{2}', audio_path)
    date_str = date_match.group(0) if date_match else ""

    concat_file_path = os.path.join(slides_dir, "concat.txt")
    with open(concat_file_path, "w", encoding="utf-8") as f:
        for idx, s in enumerate(slides_data):
            duration = max(3.0, (s["char_count"] / total_chars) * total_duration)
            slide_img_path = os.path.join(slides_dir, f"slide_{idx:02d}.png")
            create_slide_image(slide_img_path, show_type, s["title"], s["bullets"], date_str)
            
            clean_path = slide_img_path.replace("\\", "/")
            f.write(f"file '{clean_path}'\n")
            f.write(f"duration {duration:.2f}\n")

        clean_path = os.path.join(slides_dir, f"slide_{len(slides_data)-1:02d}.png").replace("\\", "/")
        f.write(f"file '{clean_path}'\n")

    print(f"[INFO] スライド動画を生成中 (全 {len(slides_data)} スライド)...", flush=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4_path
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] FFmpegでエラーが発生しました:\n{res.stderr}")
        sys.exit(1)

    print(f"[OK] 全喋り文章網羅版スライド動画の生成が完了しました: {output_mp4_path}")

def main():
    if len(sys.argv) < 4:
        print("Usage: python create_video.py <audio_path> <script_path> <artwork_path> <output_mp4_path> [show_type]")
        sys.exit(1)

    audio_path = sys.argv[1]
    script_path = sys.argv[2]
    artwork_path = sys.argv[3]
    output_mp4_path = sys.argv[4]
    show_type = sys.argv[5] if len(sys.argv) > 5 else "news"

    create_multi_slide_video(audio_path, script_path, artwork_path, output_mp4_path, show_type)

if __name__ == "__main__":
    main()
