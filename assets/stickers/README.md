# 切り抜いた素材

`materials/stickers.yaml` のレシピから `src/yogen/stickers.py` の `sticker()` で書き出した、原画の色の切り抜き（透明の地の PNG、長辺 1200px）。
ファイル名は `<モチーフ>_<番号>.png`（番号はレシピの順）。網点にした版は `halftone_sticker()` でその都度作る。

元の図版はすべて美術館のオープンアクセスのパブリックドメイン（CC0）。出典は `materials/index.yaml`。

浮世絵・版画から切り出したもの（fuji 凱風快晴、sagi 鷺娘、gaikotsu 団十郎の骸骨、shoki 鍾馗）は `method: flood`（外縁の地の色をたどって人物・山を輪郭で抜く）。
輪郭で抜いた素材だけを置く。ちぎった紙片や矩形の切り出しは使わない。
