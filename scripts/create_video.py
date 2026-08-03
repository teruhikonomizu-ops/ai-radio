"""
音声(MP3)とアートワーク画像(PNG)からYouTube用16:9 MP4動画を作成するスクリプト

使い方:
  python scripts/create_video.py <audio_path> <image_path> <output_mp4_path>
"""

import sys
import os
import subprocess

def create_video(audio_path, image_path, output_path):
    if not os.path.exists(audio_path):
        print(f"❌ 音声ファイルが見つかりません: {audio_path}")
        sys.exit(1)
    if not os.path.exists(image_path):
        print(f"❌ 画像ファイルが見つかりません: {image_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-shortest",
        output_path
    ]

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print(f"[INFO] 動画作成を開始します: {output_path}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] ffmpeg でのエラーが発生しました:\n{res.stderr}")
        sys.exit(1)

    print(f"[OK] 動画の作成が完了しました: {output_path}")

def main():
    if len(sys.argv) < 4:
        print("Usage: python create_video.py <audio_path> <image_path> <output_mp4_path>")
        sys.exit(1)
        
    audio_path = sys.argv[1]
    image_path = sys.argv[2]
    output_path = sys.argv[3]

    create_video(audio_path, image_path, output_path)

if __name__ == "__main__":
    main()
