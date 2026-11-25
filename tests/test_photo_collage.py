from yogen import photo_collage


def test_fills_without_ground_and_respects_reserve():
    img, st = photo_collage.generate(3, size=(300, 400))
    assert img.size == (300, 400)
    assert st["holes"] == 0 and st["covered"] == 1.0  # 下地が透ける画素がない
    _, st2 = photo_collage.generate(3, size=(300, 400), reserve=[(0, 0, 300, 100)])
    assert st2["holes"] == 0 and st2["objects"] < st["objects"]  # 取っておいた場所には置かない
