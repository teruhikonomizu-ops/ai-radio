# ai-radio — AIラジオ2番組の全自動クラウド生成・配信

毎朝、GitHub Actions がクラウド上で「ニュース収集 → 台本執筆(Claude) →
音声合成(AivisSpeech) → ポッドキャスト配信(RSS) → YouTube動画(立ち絵+大きな字幕)」まで無人実行する。
**PCの電源は不要。人の作業もゼロ。**

| 番組 | 実行時刻(JST) | フィードURL |
|---|---|---|
| AIデイリーニュース | 毎朝 05:00 | `https://teruhikonomizu-ops.github.io/ai-radio/news/feed.xml` |
| 世界のAIニュース | 毎朝 04:00 | `https://teruhikonomizu-ops.github.io/ai-radio/tech/feed.xml` |

スマホのポッドキャストアプリに上のフィードURLを登録すると、毎朝自動で新エピソードが届く。

## 登場キャラクター(unizomのオリジナルIP・2026-08-10導入)

番組ごとに専属の1キャラがソロで読み上げる(掛け合いではない)。画面上にキャラ名の表示はしない。
- **AIデイリーニュース**: AIアンドロイド「**ユー**」。声はAivisSpeechのmorioki
- **世界のAIニュース**: 相棒ロボット「**ゼータ**」。声はAivisSpeechのコハク候補6

どちらも元々ニュースラジオ/AIテックラジオで使っていた声で、キャラクターが変わっても声は据え置き。
見た目はHiggsfieldで1から作った完全オリジナルデザイン(`assets/characters/`、胸元にunizomロゴ入り)で、
既存の版権キャラ(ずんだもん等)とは無関係。背景も番組ごとにHiggsfieldで作った専用のテック調グラフィック
(`assets/backgrounds/`、一度作った静止画を毎日使い回す・生成コストは初回のみ)。

## 仕組み

```
GitHub Actions (毎朝・cron)
  1. scripts/collect_news.py    … 公式RSS(NHK/Yahoo!)から見出し収集 → digest.md
  2. scripts/check_digest.py    … 取得成功が半分未満なら中止(誤報防止)
  3. claude -p                  … prompts/<show>.md のルールで番組専属キャラのソロ台本+概要欄を執筆
                                   (CLAUDE_CODE_OAUTH_TOKEN シークレット=Claude定額プラン内)
  4. scripts/split_output.py    … 台本/概要欄に分割・文字数検査(不合格なら1回作り直し)
  5. scripts/tts_aivis.py       … AivisSpeech Engine(公式Dockerイメージ・CPU・無料)で音声合成
                                   → mp3 + 文単位のタイミング情報(*.segments.json)
  6. 長さ検証(5〜15分の範囲外なら公開中止) → GitHub Release にmp3を添付
  7. scripts/create_video.py    … segments.jsonを使いキャラの立ち絵(口パク)+大きな字幕を合成 → 1080p MP4
  8. scripts/upload_youtube.py  … YouTube Data API v3 で YouTube へ自動投稿
  9. scripts/make_feed.py       … docs/<show>/feed.xml を再生成 → コミット(GitHub Pagesが配信)
```

- 声: AivisSpeech(morioki=ユー役・AivisHubからDL、コハク候補6=ゼータ役・エンジン標準搭載)
- 生成済みの日は自動スキップ。`台本.txt` だけある日は音声合成から再開(手動修復の入り口)
- 失敗時はGitHubからオーナーへ通知メールが飛ぶ(Actionsの既定動作)

## フォルダ

- `.github/workflows/news.yml` / `tech.yml` … 各番組のワークフロー本体(構成は同一・番組設定だけ違う)
- `scripts/` … 収集・検査・分割・合成・動画生成・フィード生成(標準ライブラリ+Pillow)
- `prompts/news.md` / `tech.md` … 台本ルール(執筆プロンプト・キャラ設定)。文言調整はここ
- `assets/characters/` … ユー・ゼータの立ち絵(口の開閉2種類×2キャラ、背景透過PNG)
- `assets/backgrounds/` … 番組ごとの背景画像(news.png/tech.png、1920×1080)
- `radio/<show>/<日付>/` … 台本.txt・概要欄.txt・digest.md・meta.json(公開の記録)
- `docs/` … GitHub Pages(feed.xml)

## 運用メモ

- 手動実行: Actionsタブ → news-radio → Run workflow
- 作り直したい日: `radio/news/<日付>/` の `meta.json` を消して手動実行(台本ごと作り直すなら`台本.txt`も消す)
- 元の運用(ローカルPC生成+stand.fm投稿)は
  OneDrive `デスクトップ/ai記事自動/ニュースラジオ/` にあり、当面は保険として並走(2026-08-06より無効化中)
- 台本の出典・著作権方針: 公式RSSの見出し・要旨のみを素材に自分の言葉で要約(prompts/news.md 参照)
- キャラクター立ち絵を差し替えたい場合: `assets/characters/{yu,zeta}_{open,closed}.png` を同じ構図・
  同じ透過背景で置き換えるだけでよい(`scripts/create_video.py` がそのまま使う)
