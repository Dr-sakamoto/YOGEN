"""画面の密度を作るエフェクト。手法はパンクやオタクの雑誌から借り、図形と色は日本のものを使う。

  chirashi    散らし：アイコンを大きさ・向き・色をばらして撒く
  sunago      金砂子：金箔の細片を撒く（屏風の技法）。キラキラの代わりの光り物
  jimon       地紋：アイコンを敷き詰めた地の模様（金魚・達磨・髑髏…）
  surikasane  刷り重ね：同じ形を2色でずらして重ねる（版ズレ）
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

from .icons import ICONS, stamp

RGB = tuple[int, int, int]

# 明治の赤絵
YOKO: RGB = (200, 23, 79)
MURA: RGB = (93, 42, 140)
BERO: RGB = (31, 61, 115)
TOO: RGB = (232, 179, 38)
SUMI: RGB = (22, 19, 15)
KIN: RGB = (201, 164, 74)


def _icon_layer(name: str, size: int, color: RGB, angle: float = 0) -> Image.Image:
    m = stamp(name, size)
    layer = Image.new("RGBA", (size, size), (*color, 0))
    layer.putalpha(m)
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    return layer


def chirashi(
    w: int, h: int,
    names: list[str] | None = None,
    colors: list[RGB] | None = None,
    count: int = 60,
    size: tuple[int, int] = (24, 120),
    seed: int = 1,
    avoid: tuple[float, float, float] | None = None,
) -> Image.Image:
    """透明の地にアイコンを撒く。avoid=(cx, cy, r) は撒かない円（0〜1の座標）：主役の細部を空ける。"""
    r = random.Random(seed)
    names = names or list(ICONS)
    colors = colors or [YOKO, MURA, BERO, TOO, SUMI]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    placed = 0
    tries = 0
    while placed < count and tries < count * 20:
        tries += 1
        s = int(size[0] + (size[1] - size[0]) * r.random() ** 2)  # 小さいものを多く
        x, y = r.uniform(-s / 2, w - s / 2), r.uniform(-s / 2, h - s / 2)
        if avoid:
            cx, cy, rad = avoid
            if math.hypot((x + s / 2) / w - cx, (y + s / 2) / h - cy) < rad:
                continue
        layer = _icon_layer(r.choice(names), s, r.choice(colors), r.uniform(-28, 28))
        out.alpha_composite(layer, (int(x), int(y)))
        placed += 1
    return out


def sunago(
    w: int, h: int,
    density: float = 0.004,
    size: tuple[float, float] = (1.5, 7),
    band: tuple[float, float] | None = None,
    color: RGB = KIN,
    seed: int = 2,
) -> Image.Image:
    """金砂子。band=(中心y, 幅) を指定すると、その帯に集めて上下に薄くなる（雲のように）。"""
    r = random.Random(seed)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    n = int(w * h * density)
    for _ in range(n):
        x = r.uniform(0, w)
        if band:
            y = r.gauss(band[0] * h, band[1] * h)
        else:
            y = r.uniform(0, h)
        s = r.uniform(*size)
        # 不揃いな四角形の箔の細片
        pts = [(x + s * math.cos(a) * r.uniform(.5, 1.2), y + s * math.sin(a) * r.uniform(.5, 1.2))
               for a in (r.uniform(0, 6.28) + k * math.pi / 2 for k in range(4))]
        shade = r.uniform(.8, 1.15)
        c = tuple(min(255, int(v * shade)) for v in color)
        d.polygon(pts, fill=(*c, int(255 * r.uniform(.75, 1))))
    return out


def jimon(
    w: int, h: int,
    name: str = "kingyo",
    cell: int = 64,
    color: RGB = BERO,
    ground: RGB | None = None,
    offset: bool = True,
    step_y: float | None = None,
) -> Image.Image:
    """アイコンを敷き詰めた地紋。offset で段ごとに半分ずらす。"""
    out = Image.new("RGBA", (w, h), (*ground, 255) if ground else (0, 0, 0, 0))
    layer = _icon_layer(name, cell, color)
    sy = int(step_y if step_y else cell)
    row = 0
    y = -cell
    while y < h + cell:
        x0 = -cell + (cell // 2 if offset and row % 2 else 0)
        x = x0
        while x < w + cell:
            out.alpha_composite(layer, (x, y)) if 0 <= x and 0 <= y else out.paste(layer, (x, y), layer)
            x += cell
        y += sy
        row += 1
    return out


def surikasane(layer: Image.Image, under: RGB = YOKO, over: RGB | None = None, dx: int = 6, dy: int = -5) -> Image.Image:
    """透明の地のレイヤーを、下の版（under）をずらして重ねた形にする。"""
    a = layer.getchannel("A")
    w, h = layer.size
    out = Image.new("RGBA", (w + abs(dx), h + abs(dy)), (0, 0, 0, 0))
    under_l = Image.new("RGBA", layer.size, (*under, 255))
    under_l.putalpha(a)
    ox, oy = max(0, -dx), max(0, -dy)
    out.alpha_composite(under_l, (ox + dx, oy + dy))
    if over:
        top = Image.new("RGBA", layer.size, (*over, 255))
        top.putalpha(a)
        out.alpha_composite(top, (ox, oy))
    else:
        out.alpha_composite(layer, (ox, oy))
    return out


def soft_shadow(layer: Image.Image, radius: int = 8, opacity: float = .5) -> Image.Image:
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh.alpha_composite(layer)
    return sh
