"""YŌGEN のオリジナルアイコン。

どのアイコンも 100×100 の座標で、「足す（add）」と「切り抜く（cut）」の手順で定義する。
単色のシルエットで、細部は切り抜き（地が見える）で表す。
江戸の浮世絵や風俗に具体的な出典があるものだけを入れる（時代を問わない「和」の記号は入れない）。網点の図形・ステッカー・パターンの
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



ICONS = {
    # 江戸の浮世絵や風俗に具体的な出典があるものだけ
    "kingyo": ("金魚", _kingyo),      # 国芳『金魚づくし』
    "fuji": ("富士", _fuji),          # 北斎『富嶽三十六景』、富士講
    "chochin": ("提灯お化け", _chochin),  # 北斎『百物語』お岩さん
    "kitsune": ("狐面", _kitsune),    # 広重「王子装束ゑの木大晦日の狐火」
    "dokuro": ("髑髏", _dokuro),      # 国芳「相馬の古内裏」
    "oni": ("鬼面", _oni),            # 大津絵「鬼の念仏」
    "daruma": ("達磨", _daruma),      # 疱瘡よけの赤物
    "maneki": ("招き猫", _maneki),    # 今戸焼の丸〆猫
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
