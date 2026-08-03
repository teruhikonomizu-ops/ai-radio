"""
YouTube Data API v3 を使って動画を自動投稿するスクリプト

使い方:
  python scripts/upload_youtube.py <video_path> <desc_path> <show_type>

環境変数 (GitHub Secretsから渡される):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
"""

import sys
import os

def upload_video(video_path, desc_path, show_type):
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print("❌ YouTube APIの認証環境変数が不足しています。(YOUTUBE_CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN)")
        sys.exit(1)

    if not os.path.exists(video_path):
        print(f"❌ 投稿対象の動画ファイルが見つかりません: {video_path}")
        sys.exit(1)

    if not os.path.exists(desc_path):
        print(f"❌ 概要欄ファイルが見つかりません: {desc_path}")
        sys.exit(1)

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("❌ 必要な Google API ライブラリがインストールされていません。")
        print("pip install google-auth-oauthlib google-api-python-client を実行してください。")
        sys.exit(1)

    with open(desc_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    lines = content.split("\n")
    title = lines[0].strip() if lines else "AI Radio Episode"
    description = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

    # YouTubeのタイトル上限は100文字
    if len(title) > 100:
        title = title[:97] + "..."

    # 番組に応じたカテゴリーとタグの設定
    if show_type == "tech":
        category_id = "28"  # Science & Technology
        tags = ["AI", "テクノロジー", "人工知能", "AIニュース", "世界のAIニュース", "ポッドキャスト"]
        feed_url = "https://teruhikonomizu-ops.github.io/ai-radio/tech/feed.xml"
    else:
        category_id = "25"  # News & Politics
        tags = ["AI", "ニュース", "AIニュース", "デイリーニュース", "ラジオ", "ポッドキャスト"]
        feed_url = "https://teruhikonomizu-ops.github.io/ai-radio/news/feed.xml"

    description += f"\n\n---\n🎙️ この動画は全自動生成されたAIラジオ/ポッドキャストです。\nポッドキャストRSS: {feed_url}"

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print(f"[INFO] YouTube への動画アップロードを開始します: {title}", flush=True)
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"進捗: {int(status.progress() * 100)}%", flush=True)

    video_id = response.get("id")
    print("[OK] YouTube への投稿が成功しました！", flush=True)
    print(f"URL: https://www.youtube.com/watch?v={video_id}", flush=True)

    # 再生リストへの自動追加
    try:
        playlist_keyword = "世界のAIニュース" if show_type == "tech" else "AIデイリーニュース"
        pl_res = youtube.playlists().list(mine=True, part="snippet", maxResults=50).execute()
        target_pl_id = None
        for item in pl_res.get("items", []):
            if playlist_keyword in item["snippet"]["title"]:
                target_pl_id = item["id"]
                break

        if target_pl_id:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": target_pl_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            print(f"[OK] 再生リスト「{playlist_keyword}」に自動追加しました！", flush=True)
    except Exception as e:
        print(f"[NOTE] 再生リストの自動追加はスキップされました: {e}", flush=True)

def main():
    if len(sys.argv) < 4:
        print("Usage: python upload_youtube.py <video_path> <desc_path> <show_type>")
        sys.exit(1)

    video_path = sys.argv[1]
    desc_path = sys.argv[2]
    show_type = sys.argv[3]

    upload_video(video_path, desc_path, show_type)

if __name__ == "__main__":
    main()
