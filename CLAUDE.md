# YŌGEN

英語圏向けショートチャンネル「YŌGEN（妖幻）— Phantoms of the floating world」のコンテンツ工場。
浮世絵・江戸期の絵画に描かれた妖怪・異界を、美術史と社会史の視点で解説する。

## 守ること

- 台本の事実は `episodes/<id>/episode.yaml` の `research_notes` と `sources` からしか取らない。記憶で補わない。
- 画像はパブリックドメインと確認できた作品だけ（`sources.py` が met / aic の判定で止める）。
  水木しげる、アニメ・ゲームの妖怪デザイン、没後70年未満の作家、美術書や他チャンネルの画像は使わない。
- `fact_checked` と `approved` は人が進める状態。Claude が代わりに `verified: true` にしたり `yogen mark` を実行したりしない。
- 解釈は「〜という説がある」の形で書く。裏付けの弱い説を看板にしない。
- 表記：ロゴは YŌGEN、ハンドル・タグ・ファイル名は YOGEN。読みは yoh-GEN (hard g)。

## 開発

- `pip install -e ".[dev]"`、`pytest -q`（ffmpeg が必要）
- CLI は `src/yogen/cli.py`。台本の書き方は `prompts/script_system.md`、設定は `config/channel.yaml`。
