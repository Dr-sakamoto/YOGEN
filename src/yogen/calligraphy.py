"""日本語の文字をグラフィックとして使う（隷書・篆書）。英語は使わない。

書体ファイルそのものは配らず、字の形（アウトライン）を SVG のパスや画像にして使う。

  隷書  青柳隷書しも（assets/fonts/aoyagireisyosimo/）
        無料・商用可・無料での再配布可。再配布するときは同梱の「フォントの使用方法」と
        「フォントの解説」を一緒に配ること。
  篆書  未定（規約を確認できる書体が見つかっていない）
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .config import ROOT

REISHO = ROOT / "assets" / "fonts" / "aoyagireisyosimo" / "aoyagireisyosimo_ttf_2_01.ttf"


@lru_cache
def _font(path: str):
    from fontTools.ttLib import TTFont

    return TTFont(path)


def glyph_paths(text: str, font_path: Path = REISHO, vertical: bool = False, tracking: float = 0.0):
    """文字列を SVG のパスに変換する。返り値は (パスの d, 幅, 高さ)。1文字 = 1000 単位。

    vertical=True で縦書き（上から下へ）。tracking は字間（1000 単位に対する割合、負で詰める）。
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    f = _font(str(font_path))
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    k = 1000 / upm
    asc = f["hhea"].ascent * k
    ds = []
    pen_pos = 0.0
    for ch in text:
        name = cmap.get(ord(ch))
        if name is None:
            raise KeyError(f"書体に「{ch}」がありません")
        adv = (gs[name].width * k) if not vertical else 1000
        svg = SVGPathPen(gs)
        if vertical:
            # 縦書き：字の箱の上端を pen_pos に置く（y を反転）
            t = TransformPen(svg, (k, 0, 0, -k, (1000 - gs[name].width * k) / 2, pen_pos + asc * .92))
        else:
            t = TransformPen(svg, (k, 0, 0, -k, pen_pos, asc))
        gs[name].draw(t)
        ds.append(svg.getCommands())
        pen_pos += adv * (1 + tracking)
    total = pen_pos - (1000 if vertical else adv) * tracking if text else 0
    w, h = (1000, total) if vertical else (total, 1000)
    return " ".join(ds), w, h


def svg(text: str, color: str = "currentColor", vertical: bool = False, tracking: float = 0.0,
        font_path: Path = REISHO, cls: str = "") -> str:
    d, w, h = glyph_paths(text, font_path, vertical, tracking)
    return (f'<svg class="{cls}" viewBox="0 0 {w:.0f} {h:.0f}" aria-label="{text}" role="img">'
            f'<path d="{d}" fill="{color}"/></svg>')


def image(text: str, size: int, color=(22, 19, 15), font_path: Path = REISHO, vertical: bool = False):
    """動画用：透明の地に字を描いた画像（Pillow）。"""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(font_path), size)
    if vertical:
        im = Image.new("RGBA", (size, size * len(text)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, ch in enumerate(text):
            d.text((size / 2, i * size + size / 2), ch, font=font, fill=(*color, 255), anchor="mm")
        return im
    bbox = font.getbbox(text)
    im = Image.new("RGBA", (bbox[2] + 4, size + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2, 2), text, font=font, fill=(*color, 255))
    return im
