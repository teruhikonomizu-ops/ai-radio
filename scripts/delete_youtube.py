"""
誤って投稿したYouTube動画を削除する一回限りのユーティリティ

使い方: python scripts/delete_youtube.py <video_id>
環境変数: YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
"""
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("Usage: python delete_youtube.py <video_id>")
        sys.exit(1)
    video_id = sys.argv[1]

    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if not client_id or not client_secret or not refresh_token:
        print("YouTube APIの認証環境変数が不足しています。")
        sys.exit(1)

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    youtube = build("youtube", "v3", credentials=creds)

    try:
        youtube.videos().delete(id=video_id).execute()
        print(f"[OK] 削除しました: {video_id}")
    except HttpError as e:
        print(f"[ERROR] 削除に失敗しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
