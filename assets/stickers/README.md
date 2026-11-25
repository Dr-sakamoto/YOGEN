# 切り抜いた素材

`materials/stickers.yaml` のレシピから `src/yogen/stickers.py` の `sticker()` で書き出した、原画の色の切り抜き（透明の地の PNG、長辺 1200px）。
ファイル名は `<モチーフ>_<番号>.png`（番号はレシピの順）。網点にした版は `halftone_sticker()` でその都度作る。

元の図版はすべて美術館のオープンアクセスのパブリックドメイン（CC0）。出典は `materials/index.yaml`。

浮世絵・版画から切り出したもの（sagi 鷺娘、gaikotsu 団十郎の骸骨、shoki 鍾馗、koheiji 小平次、sarayashiki お菊、nami 神奈川沖浪裏）は
`method: flood`（人物の輪郭で抜く）または `torn`（ちぎった紙片）。
