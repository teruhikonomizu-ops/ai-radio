# ai-radio — AIラジオ2番組の全自動クラウド生成・配信

毎朝、GitHub Actions がクラウド上で「ニュース収集 → 台本執筆(Claude) → 音声合成(AivisSpeech) →
ポッドキャスト配信(RSS)」まで無人実行する。**PCの電源は不要。人の作業もゼロ。**

| 番組 | 実行時刻(JST) | フィードURL |
|---|---|---|
| AIデイリーニュース | 毎朝 05:00 | `https://teruhikonomizu-ops.github.io/ai-radio/news/feed.xml` |
| 世界のAIニュース | (準備中・毎朝04:00予定) | `https://teruhikonomizu-ops.github.io/ai-radio/tech/feed.xml` |

スマホのポッドキャストアプリに上のフィードURLを登録すると、毎朝自動で新エピソードが届く。

## 仕組み

```
GitHub Actions (毎朝・cron)
  1. scripts/collect_news.py   … 公式RSS(NHK/Yahoo!)から見出し収集 → digest.md
  2. scripts/check_digest.py   … 取得成功が半分未満なら中止(誤報防止)
  3. claude -p                 … prompts/<show>.md のルールで台本+概要欄を執筆
                                  (CLAUDE_CODE_OAUTH_TOKEN シークレット=Claude定額プラン内)
  4. scripts/split_output.py   … 台本/概要欄に分割・文字数検査(不合格なら1回作り直し)
  5. scripts/tts_aivis.py      … AivisSpeech Engine(公式Dockerイメージ・CPU)で音声合成 → mp3
  6. 長さ検証(5〜15分の範囲外なら公開中止) → GitHub Release にmp3を添付
  7. scripts/make_feed.py      … docs/<show>/feed.xml を再生成 → コミット(GitHub Pagesが配信)
```

- 声: morioki (AivisHub `baaae3c0-7b22-4605-8ba5-80c959b41a48`)。エンジンデータはActionsキャッシュで高速化
- 生成済みの日は自動スキップ。`台本.txt` だけある日は音声合成から再開(手動修復の入り口)
- 失敗時はGitHubからオーナーへ通知メールが飛ぶ(Actionsの既定動作)

## フォルダ

- `.github/workflows/news.yml` … ニュースラジオのワークフロー本体
- `scripts/` … 収集・検査・分割・合成・フィード生成(全て標準ライブラリのみ)
- `prompts/news.md` … 台本ルール(執筆プロンプト)。文言調整はここ
- `radio/<show>/<日付>/` … 台本.txt・概要欄.txt・digest.md・meta.json(公開の記録)
- `docs/` … GitHub Pages(feed.xml・アートワーク)

## 運用メモ

- 手動実行: Actionsタブ → news-radio → Run workflow
- 作り直したい日: `radio/news/<日付>/` の `meta.json` を消して手動実行(台本ごと作り直すなら`台本.txt`も消す)
- 元の運用(ローカルPC生成+stand.fm投稿)は
  OneDrive `デスクトップ/ai記事自動/ニュースラジオ/` にあり、当面は保険として並走
- 台本の出典・著作権方針: 公式RSSの見出し・要旨のみを素材に自分の言葉で要約(prompts/news.md 参照)
