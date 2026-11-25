from yogen import photo_collage


def test_fills_without_ground_and_respects_reserve():
    img, st = photo_collage.generate(3, size=(300, 400), max_obj=60)
    assert img.size == (300, 400)
    assert st["covered"] > .8 and st["bare"] < .25
    img2, st2 = photo_collage.generate(3, size=(300, 400), max_obj=60, reserve=[(0, 0, 300, 100)])
    assert st2["covered"] >= .25  # 取っておいた場所は埋まった扱い
