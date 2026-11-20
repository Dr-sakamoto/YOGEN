# YŌGEN コンテンツ工場

浮世絵の妖怪ショート（YŌGEN／妖幻）を作るための仕組みです。
「ネタ決め → 素材取得 → 台本の下書き → 事実確認 → 試写 → 予約投稿」の流れを、このリポジトリと GitHub Actions で回します。

人が決めるのは、**ネタとリサーチメモ**、**事実確認**、**試写のOK**の3つだけです。ほかは機械がやります。

## 流れ

```
 人          episodes/<id>/episode.yaml にネタと一次資料のメモを書く
 機械        yogen fetch   … 美術館APIから作品画像を取得（パブリックドメイン以外は止まる）
 機械        yogen script  … Claudeが台本・カメラワーク・タイトル・説明文を下書き → PR
 人   ★      claims（事実主張の一覧）を一次資料で確認して verified: true にする
 機械        CI が試写動画を作る（PRの Artifacts → previews）
 人   ★      試写を見て OK なら publish_at を入れ、yogen mark で approved にしてマージ
 機械        Publish ワークフローがレンダリング → YouTubeに非公開で予約投稿
 YouTube     publish_at の日時に自動で公開
```

★の2か所を飛ばすと先に進めないようにしてあります（`yogen mark` が未確認の claims を検出すると止まる）。

## エピソードの状態

| 状態 | 意味 | 誰が進めるか |
|---|---|---|
| `draft` | 企画・リサーチ中 | 人 |
| `scripted` | 台本の下書きができた | `yogen script` |
| `fact_checked` | claims をすべて確認した | 人（`yogen mark <id> fact_checked`） |
| `approved` | 試写OK、公開日が決まった | 人（`yogen mark <id> approved`） |
| `scheduled` | YouTubeに予約投稿済み | Publish ワークフロー |

## ローカルで使う

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # ffmpeg も必要
yogen new 0002-soma-no-furudairi --title "The giant skeleton"
yogen fetch 0002-soma-no-furudairi
yogen script 0002-soma-no-furudairi   # ANTHROPIC_API_KEY が必要
yogen check 0002-soma-no-furudairi
yogen render 0002-soma-no-furudairi --tts silent   # APIキーなしで無音の試写
yogen status
```

APIキーなしで試写の仕組みだけ見たいときは、`tests/fixtures/sample_script.yaml` を
`episodes/0001-omori-hikoshichi/script.yaml` にコピーして `yogen render 0001-omori-hikoshichi --tts silent`。

## ディレクトリ

```
config/channel.yaml        チャンネル設定（モデル、尺、音声、公開時刻など）
prompts/script_system.md   台本の書き方（動画の型・事実のルール）。ここを直すと全回の台本が変わる
episodes/<id>/episode.yaml 1本ごとの企画・メモ・状態（人が書く）
episodes/<id>/script.yaml  台本（Claudeが下書き、人が直す）
src/yogen/                 工場本体
.github/workflows/         CI（テスト＋試写）、Draft script、Publish
```

画像・音声・完成動画は git に入れません（Actions で毎回作り直します）。

## 初期設定（一度だけ）

### 1. GitHub Secrets

| Secret | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | 台本の下書き |
| `ELEVENLABS_API_KEY` | ナレーション（`config/channel.yaml` の `tts.provider` を `elevenlabs` にし、`elevenlabs_voice_id` を設定） |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` | 投稿 |

### 2. YouTube の投稿権限

1. Google Cloud でプロジェクトを作り、YouTube Data API v3 を有効にする
2. OAuth 同意画面を作り、OAuth クライアント（デスクトップアプリ）を作って JSON をダウンロード
3. 手元で `pip install -e ".[auth]"` → `yogen auth client_secret.json` → ブラウザでチャンネルのアカウントを選ぶ
4. 表示された3つの値を GitHub Secrets に登録

**注意：** 審査（監査）を受けていない API プロジェクトからアップロードした動画は、
YouTube 側で「非公開」に固定されます。公開予約を効かせるには、Google の
YouTube API Services の監査を申請して通す必要があります。
通るまでは、アップロードまで自動で行い、公開は YouTube Studio で手で切り替える運用になります。

また、OAuth 同意画面が「テスト」状態のままだと refresh token が7日で切れます。「本番」に切り替えてください。

## 収益化ポリシーとの関係

YouTube は量産・反復的な動画（inauthentic content）を収益化の対象外にしています。この工場は「量産」ではなく
「人が調べて確認した解説を、手間なく形にする」ためのものです。そのため次のようにしています。

- 事実は人が書いたリサーチメモからしか取らない。主張はすべて claims として人が確認する
- 毎回カメラワーク（ズーム・パン）を入れ、静止画のスライドショーにしない
- 型は固定だが、フック・論点・着地は毎回変える（`prompts/script_system.md`）
- 試写を人が見てから approved にする
