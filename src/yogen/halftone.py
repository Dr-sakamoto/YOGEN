"""文様の網点（もんようの あみてん）。

雑誌印刷の網点と同じ仕組みで、画像の暗いところほど図形を大きく描く。
ただし点ではなく、江戸・妖怪の図形を反復する。

  uroko     鱗紋：三角。能では鬼女や蛇の化身の装束の柄
  hitodama  人魂：尾を引く火の玉
  medama    目玉：一つ目の妖怪の目
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

SS = 4  # アンチエイリアス用の拡大率


def _uroko(d: ImageDraw.ImageDraw, cx, cy, s, color, row, gap=None):
    # 段ごとに上下を反転させると鱗紋の並びになる
    h = s * 0.9
    if row % 2 == 0:
        pts = [(cx - s / 2, cy + h / 2), (cx + s / 2, cy + h / 2), (cx, cy - h / 2)]
    else:
        pts = [(cx - s / 2, cy - h / 2), (cx + s / 2, cy - h / 2), (cx, cy + h / 2)]
    d.polygon(pts, fill=color)


def _hitodama(d: ImageDraw.ImageDraw, cx, cy, s, color, row, gap=None):
    r = s * 0.32
    bx, by = cx - s * 0.12, cy + s * 0.14
    d.ellipse((bx - r, by - r, bx + r, by + r), fill=color)
    # 尾：右上へ流れて細くなる
    tail = []
    for i in range(13):
        t = i / 12
        ang = -math.pi / 4 - t * 0.9
        rr = r * (1 - t) * 0.95
        px = bx + math.cos(-math.pi / 4) * r * 0.2 + t * s * 0.55
        py = by - t * s * 0.55 + math.sin(t * math.pi) * s * 0.08
        tail.append((px + math.cos(ang + math.pi / 2) * rr, py + math.sin(ang + math.pi / 2) * rr))
    back = []
    for i in range(12, -1, -1):
        t = i / 12
        ang = -math.pi / 4 - t * 0.9
        rr = r * (1 - t) * 0.95
        px = bx + math.cos(-math.pi / 4) * r * 0.2 + t * s * 0.55
        py = by - t * s * 0.55 + math.sin(t * math.pi) * s * 0.08
        back.append((px - math.cos(ang + math.pi / 2) * rr, py - math.sin(ang + math.pi / 2) * rr))
    d.polygon(tail + back, fill=color)


def _medama(d: ImageDraw.ImageDraw, cx, cy, s, color, row, gap=(0, 0, 0, 0)):
    # 目の形：左右が尖ったアーモンドに、白目の輪と黒目
    w, h = s * 0.46, s * 0.3
    almond = [(cx + w * math.cos(a), cy + h * math.sin(a) * abs(math.cos(a)) ** 0.25)
              for a in (math.pi * 2 * i / 32 for i in range(32))]
    d.polygon(almond, fill=color)
    pr = h * 0.62
    if pr > 2:
        d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=gap)
        pp = pr * 0.62
        d.ellipse((cx - pp, cy - pp, cx + pp, cy + pp), fill=color)


SHAPES = {"uroko": _uroko, "hitodama": _hitodama, "medama": _medama}


def monyou_halftone(
    src: Image.Image,
    shape: str = "uroko",
    cell: int = 18,
    ink: tuple[int, int, int] = (22, 19, 15),
    paper: tuple[int, int, int] | None = None,
    gamma: float = 1.0,
    min_size: float = 0.12,
    invert: bool = False,
) -> Image.Image:
    """src を文様の網点に変換する。paper を指定しなければ透明の地。

    shape は uroko / hitodama / medama か、icons.py のアイコン名（daruma, kingyo …）。

    invert=True は暗い地に明るいインクで刷るとき：明るいところほど図形を大きくする。
    図形は網の目より大きくならないので、隣とつながって線にならない。
    """
    # 浮世絵は明るい中間調が多いので、明暗を均してから網にする
    g = ImageOps.equalize(ImageOps.grayscale(src))
    w, h = g.size
    out = Image.new("RGBA", (w * SS, h * SS), (*paper, 255) if paper else (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    color = (*ink, 255)
    if shape in SHAPES:
        draw = SHAPES[shape]
    else:
        # icons.py のアイコンも図形にできる
        from .icons import stamp as _stamp

        def draw(d, cx, cy, s, color, row, gap):
            size = max(2, int(s))
            m = _stamp(shape, size)
            out.paste(Image.new("RGBA", (size, size), color), (int(cx - size / 2), int(cy - size / 2)), m)
    gap = (*paper, 255) if paper else (0, 0, 0, 0)
    row = 0
    y = cell / 2
    while y < h + cell:
        x = cell / 2 + (cell / 2 if row % 2 else 0)
        while x < w + cell:
            box = (max(0, int(x - cell / 2)), max(0, int(y - cell / 2)),
                   min(w, int(x + cell / 2)), min(h, int(y + cell / 2)))
            if box[2] > box[0] and box[3] > box[1]:
                tone = sum(g.crop(box).getdata()) / ((box[2] - box[0]) * (box[3] - box[1]) * 255)
                amount = (tone if invert else 1 - tone) ** gamma
                if amount > min_size:
                    draw(d, x * SS, y * SS, cell * SS * (0.2 + 0.8 * amount), color, row, gap)
            x += cell
        y += cell * 0.87
        row += 1
    return out.resize((w, h), Image.LANCZOS)


def render_file(src_path: Path, dest: Path, **kw) -> Path:
    with Image.open(src_path) as im:
        monyou_halftone(im.convert("RGB"), **kw).save(dest)
    return dest
