# YŌGEN

英語圏向けショートチャンネル「YŌGEN（妖幻）— Phantoms of the floating world」のコンテンツ工場。
浮世絵・江戸期の絵画に描かれた妖怪・異界を、美術史と社会史の視点で解説する。

## 会話

- ユーザーとの会話・報告・説明はすべて日本語で書く。動画が英語圏向けでも、ユーザーへの返答は英語にしない。
  英語にするのは動画の中身（台本・字幕・タイトル・説明文）だけ。

## 守ること

- 台本の事実は `episodes/<id>/episode.yaml` の `research_notes` と `sources` からしか取らない。記憶で補わない。
- 画像はパブリックドメインと確認できた作品だけ（`sources.py` が met / aic の判定で止める）。
  水木しげる、アニメ・ゲームの妖怪デザイン、没後70年未満の作家、美術書や他チャンネルの画像は使わない。
- `fact_checked` と `approved` は人が進める状態。Claude が代わりに `verified: true` にしたり `yogen mark` を実行したりしない。
- 解釈は「〜という説がある」の形で書く。裏付けの弱い説を看板にしない。
- 表記：ロゴは篆書の「妖幻」、英字の題字は小文字の yōgen、ハンドル・タグ・ファイル名は YOGEN。読みは yoh-GEN (hard g)。

## 開発

- `pip install -e ".[dev]"`、`pytest -q`（ffmpeg が必要）
- CLI は `src/yogen/cli.py`。台本の書き方は `prompts/script_system.md`、設定は `config/channel.yaml`。

## ブランド（決定）

- ロゴは篆書の「妖幻」のみ。英字の題字は小文字「yōgen」で、藤黄の地に黒で使う。
- どちらもピンボケ処理（`src/yogen/degrade.py` の `defocus`）。設定値と使い方は `src/yogen/brand.py`。
  書き出し済みの画像は `assets/brand/`。
- 色：洋紅・紫・ベロ藍・藤黄・墨・胡粉の6色（`src/yogen/palette.py`）。地は墨、差し色は洋紅・紫・ベロ藍・藤黄から
  1〜3色をその回ごとに選ぶ（episode.yaml の `colors`）。藤黄は英字の題字の地にも使う。
- 切り抜いた素材（`src/yogen/stickers.py`、レシピは `materials/stickers.yaml`）には色を付けない。
  網点（`halftone_sticker`）にして色面に重ねる。墨の地では胡粉の点、色の地では墨の点。主役の作品だけ原画の色。
- 切り抜きは輪郭で抜いたものだけ。ちぎった紙片・矩形の切り出し（`torn` など）は禁止。輪郭が取れない図版は素材に載せない。
- 参考資料（Pinterest のイメージボードなど）は `docs/references.md`。
