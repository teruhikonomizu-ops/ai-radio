"""
YouTube Data API v3 初回認証用スクリプト

使い方:
1. Google Cloud Consoleで作成した「クライアント秘密鍵 JSON ファイル」を
   `client_secret.json` という名前で ai-radio リポジトリ直下に保存します。
2. `python scripts/get_youtube_token.py` を実行します。
3. ブラウザが開くので `rmunizom@gmail.com` でログインし、権限を許可します。
4. 画面に表示された CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN をメモし、GitHub Secretsに設定します。
"""

import os
import json
import sys

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        except Exception:
            pass

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[ERROR] 必要なライブラリがインストールされていません。", flush=True)
        print("以下のコマンドを実行してください:", flush=True)
        print("pip install google-auth-oauthlib google-api-python-client", flush=True)
        sys.exit(1)

    # YouTube投稿に必要なスコープ
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    client_secret_file = os.path.join(project_root, 'client_secret.json')
    if not os.path.exists(client_secret_file):
        client_secret_file = os.path.join(script_dir, 'client_secret.json')
        
    if not os.path.exists(client_secret_file):
        print("[ERROR] `client_secret.json` が見つかりません。", flush=True)
        print("Google Cloud Console からダウンロードした OAuth クライアント JSON を `client_secret.json` として配置してください。", flush=True)
        sys.exit(1)

    print("認証プロセスを開始します。ブラウザが開かない場合は自動生成されたURLをご確認ください...", flush=True)
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    
    creds = flow.run_local_server(port=8080, open_browser=True)

    print("\n" + "="*60, flush=True)
    print("認証成功！以下の情報を GitHub リポジトリの Secrets に設定してください。", flush=True)
    print("="*60, flush=True)
    
    with open(client_secret_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        installed_or_web = data.get('installed') or data.get('web') or {}
        client_id = installed_or_web.get('client_id')
        client_secret = installed_or_web.get('client_secret')

    print(f"YOUTUBE_CLIENT_ID     : {client_id}", flush=True)
    print(f"YOUTUBE_CLIENT_SECRET : {client_secret}", flush=True)
    print(f"YOUTUBE_REFRESH_TOKEN : {creds.refresh_token}", flush=True)
    print("="*60 + "\n", flush=True)

if __name__ == '__main__':
    main()


