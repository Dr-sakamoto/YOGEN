"""YŌGEN のオリジナルアイコン。

どのアイコンも 100×100 の座標で、「足す（add）」と「切り抜く（cut）」の手順で定義する。
単色のシルエットで、細部は切り抜き（地が見える）で表す。網点の図形・ステッカー・パターンの
どれにも使えるように、細い線は使わない。

同じ定義から、PNG（Pillow で直接描く。透明の地）と SVG（マスクで切り抜き）を出す。
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

Point = tuple[float, float]


# ---------- 形の部品（すべて多角形の点列にする） ----------

def ell(cx, cy, rx, ry, rot=0.0, n=56) -> list[Point]:
    r = math.radians(rot)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)))
    return pts


def circ(cx, cy, r, n=48) -> list[Point]:
    return ell(cx, cy, r, r, 0, n)


def rect(x, y, w, h) -> list[Point]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def rrect(x, y, w, h, r, n=6) -> list[Point]:
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def path(*segs, n=14) -> list[Point]:
    """path((x0,y0), ('Q', (cx,cy), (x1,y1)), (x2,y2), ...)：直線と2次ベジェの混在。"""
    pts: list[Point] = []
    cur = None
    for s in segs:
        if isinstance(s[0], str):
            _, c, p1 = s
            for i in range(1, n + 1):
                t = i / n
                pts.append(((1 - t) ** 2 * cur[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
                            (1 - t) ** 2 * cur[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]))
            cur = p1
        else:
            pts.append(s)
            cur = s
    return pts


def mirror(pts: list[Point]) -> list[Point]:
    return [(100 - x, y) for x, y in pts]


A, C = "add", "cut"


# ---------- アイコン ----------

def _daruma():
    brow = path((36, 39), ("Q", (42, 34), (48, 38.5)), ("Q", (42, 37), (36, 39)))
    return [
        (A, ell(50, 56, 37, 39)),
        # 頭巾の縁（金の縁取り）の細い輪と、その内側の顔
        (C, ell(50, 45, 24.5, 20)), (A, ell(50, 45, 22, 17.5)),
        (C, ell(50, 46, 19, 15)),
        (A, circ(43, 46, 3.8)), (A, circ(57, 46, 3.8)),
        (A, brow), (A, mirror(brow)),
        (A, path((37, 54.5), ("Q", (44, 49), (50, 54)), ("Q", (56, 49), (63, 54.5)), ("Q", (56, 58.5), (50, 56.5)), ("Q", (44, 58.5), (37, 54.5)))),
    ]


def _kingyo():
    return [
        (A, ell(40, 50, 24, 17)),
        (A, path((58, 50), ("Q", (68, 33), (91, 24)), ("Q", (80, 41), (85, 50)), ("Q", (80, 59), (91, 76)), ("Q", (68, 67), (58, 50)))),
        (A, [(30, 37), (40, 23), (54, 36)]),
        (A, path((40, 64), ("Q", (46, 78), (54, 66)))),
        (C, circ(27, 46, 5.4)), (A, circ(27, 46, 2.8)),
        (C, path((37, 38), ("Q", (44, 50), (37, 62)), ("Q", (40, 50), (37, 38)))),
        (C, path((65, 43), ("Q", (75, 38), (84, 32)), ("Q", (75, 41), (65, 45)))),
        (C, path((65, 57), ("Q", (75, 62), (84, 68)), ("Q", (75, 59), (65, 55)))),
    ]


def _matsu():
    trunk = [(46, 92), (54, 92), (54, 66), (63, 52), (59, 49), (52, 59), (51, 40), (46, 40), (47, 58), (40, 50), (36, 53), (46, 66)]
    ops = [(A, trunk)]
    for cx, cy, rx, ry in ((50, 30, 27, 9), (28, 49, 18, 7.5), (71, 46, 20, 8), (50, 14, 15, 6.5)):
        ops.append((A, ell(cx, cy, rx, ry)))
    for cx, cy, rx in ((50, 33, 20), (28, 51.5, 12), (71, 48.5, 14), (50, 16, 9)):
        ops.append((C, ell(cx, cy, rx, 1.3)))
    return ops


def _take():
    ops = [(A, rrect(34, 6, 11, 88, 3)), (A, rrect(53, 22, 9, 72, 3))]
    for y in (26, 48, 70):
        ops.append((C, rect(34, y, 11, 1.8)))
    for y in (40, 60, 80):
        ops.append((C, rect(53, y, 9, 1.8)))
    for cx, cy, rot in ((73, 28, -28), (76, 40, 8), (22, 50, 28), (24, 37, -18), (70, 70, -20)):
        ops.append((A, ell(cx, cy, 14, 3.4, rot)))
    return ops


def _ume():
    ops = []
    for k in range(5):
        a = math.radians(-90 + 72 * k)
        ops.append((A, circ(50 + 22 * math.cos(a), 50 + 22 * math.sin(a), 15.5)))
    ops.append((A, circ(50, 50, 15)))
    ops.append((C, circ(50, 50, 7.5)))
    ops.append((A, circ(50, 50, 3.2)))
    for k in range(5):
        a = math.radians(-54 + 72 * k)
        ops.append((C, circ(50 + 12.5 * math.cos(a), 50 + 12.5 * math.sin(a), 1.8)))
    return ops


def _fuji():
    snow = [(30, 37), (37, 45), (43, 38), (50, 47), (57, 38), (63, 45), (70, 37), (68.5, 34), (63, 41), (57, 34), (50, 43), (43, 34), (37, 41), (31.5, 34)]
    return [
        (A, [(4, 84), (37, 25), (43, 22), (50, 25.5), (57, 22), (63, 25), (96, 84)]),
        (C, snow),
        (A, ell(26, 80, 18, 6.5)), (A, ell(50, 83, 21, 7)), (A, ell(75, 80, 18, 6.5)),
        (C, ell(26, 81.5, 12, 1.3)), (C, ell(50, 84.5, 14, 1.3)), (C, ell(75, 81.5, 12, 1.3)),
    ]


def _chochin():
    ops = [(A, rrect(41, 8, 18, 7, 2)), (A, rrect(41, 85, 18, 7, 2)), (A, ell(50, 50, 29, 37))]
    for y in (22, 32, 64, 74):
        ops.append((C, rect(16, y, 68, 1.7)))
    ops += [
        (C, ell(50, 46, 12, 9)), (A, circ(50, 46, 4.4)),
        (C, path((40, 58), ("Q", (50, 66), (60, 58)), ("Q", (50, 61), (40, 58)))),
        (A, path((50, 61), ("Q", (54, 72), (49, 78)), ("Q", (46, 70), (50, 61)))),
    ]
    return ops


def _hitodama():
    return [
        (A, circ(40, 64, 21)),
        (A, path((22, 56), ("Q", (34, 34), (76, 6)), ("Q", (62, 28), (61, 58)))),
        (C, path((30, 64), ("Q", (34, 52), (44, 50)), ("Q", (36, 56), (32, 68)))),
    ]


def _medama():
    # 左右が尖ったレンズ形
    almond = path((6, 54), ("Q", (50, 14), (94, 54)), ("Q", (50, 94), (6, 54)), n=28)
    ops = [(A, almond), (C, circ(50, 54, 15)), (A, circ(50, 54, 9)), (C, circ(46.5, 50.5, 2.6))]
    for k in range(5):
        x = 22 + 14 * k
        top = 36 - (2 - abs(k - 2)) * 3
        ops.append((A, [(x - 2.6, top + 6), (x + 2.6, top + 6), (x + (k - 2) * 2.2, top - 10)]))
    return ops


def _torii():
    return [
        (A, [(3, 16), (14, 22), (86, 22), (97, 16), (93, 29), (7, 29)]),
        (A, rect(14, 39, 72, 6.5)),
        (A, rect(23, 29, 8, 63)), (A, rect(69, 29, 8, 63)),
        (A, rect(46, 29, 8, 10)),
        (C, rect(21, 92, 12, 0.1)),
    ]


def _hyotan():
    return [
        (A, circ(50, 67, 25)), (A, circ(50, 35, 16)), (A, rrect(46.5, 9, 7, 13, 2)),
        (A, path((54, 14), ("Q", (64, 6), (70, 14)), ("Q", (62, 10), (54, 17)))),
        (C, rect(36, 47, 28, 1.5)), (C, rect(36, 53, 28, 1.5)),
        (C, path((34, 72), ("Q", (38, 84), (50, 87)), ("Q", (40, 82), (34, 72)))),
    ]


def _kasa():
    canopy = path((8, 50), ("Q", (12, 14), (50, 8)), ("Q", (88, 14), (92, 50)),
                  ("Q", (84, 44), (76, 51)), ("Q", (68, 44), (59, 51)), ("Q", (50, 44), (41, 51)),
                  ("Q", (32, 44), (24, 51)), ("Q", (16, 44), (8, 50)))
    ops = [(A, canopy)]
    for x0 in (24, 41, 59, 76):
        ops.append((C, [(50, 10), (50.8, 10), (x0 + .6, 49), (x0 - .6, 49)]))
    ops += [
        (C, circ(50, 30, 8.5)), (A, circ(50, 30, 4.2)),
        (A, path((45, 47), ("Q", (47, 66), (56, 70)), ("Q", (58, 58), (52, 47)))),
        (A, rect(48, 50, 4, 32)),
        (A, rrect(38, 82, 24, 5, 1.5)), (A, rect(41, 87, 4, 5)), (A, rect(55, 87, 4, 5)),
    ]
    return ops


def _kitsune():
    eye = path((28, 50), ("Q", (37, 42), (45, 50)), ("Q", (36, 54), (28, 50)))
    mark = path((30, 30), ("Q", (34, 36), (40, 34)), ("Q", (35, 33), (30, 30)))
    return [
        (A, [(16, 12), (34, 36), (50, 34), (66, 36), (84, 12), (82, 50), (66, 74), (50, 92), (34, 74), (18, 50)]),
        (C, eye), (C, mirror(eye)),
        (C, mark), (C, mirror(mark)),
        (C, ell(50, 84, 3.6, 2.4)),
        (C, path((40, 68), ("Q", (50, 74), (60, 68)), ("Q", (50, 71), (40, 68)))),
    ]


def _dokuro():
    ops = [
        (A, ell(50, 44, 31, 31)), (A, rrect(33, 60, 34, 24, 5)),
        (C, ell(38, 47, 8.5, 9.5)), (C, ell(62, 47, 8.5, 9.5)),
        (C, [(50, 57), (45.5, 66), (54.5, 66)]),
        (C, rect(33, 72, 34, 1.8)),
    ]
    for x in (41, 49.1, 57.2):
        ops.append((C, rect(x, 73.8, 1.8, 10.2)))
    return ops


def _oni():
    eye = [(28, 46), (45, 51), (43, 58), (31, 56)]
    horn = [(26, 36), (17, 5), (37, 28)]
    fang = [(37, 73), (42, 73), (39.5, 81)]
    return [
        (A, ell(50, 59, 33, 34)), (A, horn), (A, mirror(horn)),
        (C, eye), (C, mirror(eye)),
        (C, [(31, 72), (69, 72), (64, 84), (36, 84)]),
        (A, fang), (A, mirror(fang)),
        (C, path((40, 36), ("Q", (50, 42), (60, 36)), ("Q", (50, 39), (40, 36)))),
    ]


def _seigaiha():
    return [
        (A, circ(50, 64, 40)), (C, circ(50, 64, 31)), (A, circ(50, 64, 24)),
        (C, circ(50, 64, 15)), (A, circ(50, 64, 8)),
        (C, rect(0, 64, 100, 40)),
    ]


def _maneki():
    eye = path((34, 38), ("Q", (39, 33), (44, 38)), ("Q", (39, 35.5), (34, 38)))
    ear = [(29, 30), (31, 11), (45, 22)]
    return [
        (A, ell(48, 70, 27, 25)),
        (A, ell(48, 38, 22, 18)),
        (A, ear), (A, [(100 - 4 - x, y) for x, y in ear]),
        # 上げた左手（向かって右）
        (A, rrect(64, 12, 14, 34, 7)), (A, ell(71, 50, 9, 7)),
        (C, rect(66.5, 15, 1.6, 6)), (C, rect(70.2, 14, 1.6, 7)), (C, rect(73.9, 15, 1.6, 6)),
        (C, eye), (C, [(100 - 4 - x, y) for x, y in eye]),
        (C, ell(48, 46, 2.4, 1.6)),
        (C, path((43, 49), ("Q", (45.5, 52), (48, 49.5)), ("Q", (50.5, 52), (53, 49)), ("Q", (50.5, 51), (48, 48.5)), ("Q", (45.5, 51), (43, 49)))),
        # 首輪と鈴
        (C, path((28, 52), ("Q", (48, 62), (68, 52)), ("Q", (48, 59), (28, 52)))),
        (A, circ(48, 60, 4.6)), (C, rect(44.5, 60, 7, 1.2)),
        # 抱えた小判
        (C, ell(48, 78, 10.5, 13.5)), (A, ell(48, 78, 8, 11)),
        (C, rect(43, 74, 10, 1.2)), (C, rect(43, 78, 10, 1.2)), (C, rect(43, 82, 10, 1.2)),
    ]


def _tai():
    ops = [
        (A, path((6, 54), ("Q", (26, 22), (60, 32)), ("Q", (74, 38), (76, 52)), ("Q", (66, 68), (40, 70)), ("Q", (18, 70), (6, 54)))),
        (A, [(70, 50), (95, 26), (88, 50), (95, 75)]),
        (A, path((40, 70), ("Q", (46, 80), (56, 68)))),
    ]
    # 背びれのとげ
    for i in range(6):
        x = 26 + i * 7.5
        y = 31 - math.sin(i / 5 * math.pi) * 4
        ops.append((A, [(x - 3, y + 6), (x + 4, y + 5), (x + 2.5, y - 8)]))
    ops += [
        (C, circ(19, 47, 4.8)), (A, circ(19, 47, 2.4)),
        (C, path((28, 40), ("Q", (34, 52), (28, 64)), ("Q", (31, 52), (28, 40)))),
        (C, path((5, 56), ("Q", (10, 57), (13, 55)), ("Q", (10, 58.5), (5, 56)))),
    ]
    # うろこ
    for cx, cy in ((44, 46), (54, 44), (64, 47), (48, 56), (58, 56), (40, 60)):
        ops.append((C, path((cx - 4, cy - 3), ("Q", (cx + 2, cy), (cx - 4, cy + 3)), ("Q", (cx - .5, cy), (cx - 4, cy - 3)))))
    return ops


ICONS = {
    "maneki": ("招き猫", _maneki), "tai": ("鯛", _tai),
    "daruma": ("達磨", _daruma), "kingyo": ("金魚", _kingyo), "matsu": ("松", _matsu), "take": ("竹", _take),
    "ume": ("梅", _ume), "fuji": ("富士", _fuji), "hyotan": ("瓢箪", _hyotan), "torii": ("鳥居", _torii),
    "chochin": ("提灯お化け", _chochin), "hitodama": ("人魂", _hitodama), "medama": ("目玉", _medama),
    "kasa": ("唐傘お化け", _kasa), "kitsune": ("狐面", _kitsune), "dokuro": ("髑髏", _dokuro),
    "oni": ("鬼面", _oni), "seigaiha": ("青海波", _seigaiha),
}


def ops(name: str):
    return ICONS[name][1]()


# ---------- 出力 ----------

@lru_cache(maxsize=256)
def stamp(name: str, size: int) -> Image.Image:
    """アイコンのアルファマスク（L、255=インク）。size×size。"""
    ss = 4
    S = size * ss
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    k = S / 100
    for op, pts in ops(name):
        d.polygon([(x * k, y * k) for x, y in pts], fill=255 if op == A else 0)
    return im.resize((size, size), Image.LANCZOS)


def png(name: str, size: int, color=(22, 19, 15)) -> Image.Image:
    im = Image.new("RGBA", (size, size), (*color, 0))
    im.putalpha(stamp(name, size))
    return im


def svg(name: str) -> str:
    """currentColor で塗る SVG。切り抜きはマスク。"""
    def poly(pts, fill):
        return f'<polygon fill="{fill}" points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>'
    body = "".join(poly(p, "#fff" if op == A else "#000") for op, p in ops(name))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'<title>{ICONS[name][0]}</title>'
            f'<mask id="m-{name}" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">{body}</mask>'
            f'<rect width="100" height="100" fill="currentColor" mask="url(#m-{name})"/></svg>')


def export(dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for name in ICONS:
        p = dest / f"{name}.svg"
        p.write_text(svg(name), encoding="utf-8")
        png(name, 512).save(dest / f"{name}.png")
        out.append(p)
    return out
