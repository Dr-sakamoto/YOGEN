"""作品ごとの色を、その作品の顔料から取る。

  shu   主色   … 一文字ぼかしの帯と、版ズレ文字のずらす版に使う。作品の中の濃い色
  sashi 差し色 … 題箋に使う。作品の中で一番目立つ暖色

固定の色（胡粉の白・墨）は変えない。自動で取った色が合わないときは
episode.yaml の palette: {shu: "#xxxxxx", sashi: "#xxxxxx"} で上書きする。
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from PIL import Image

GOFUN = "#eeefeb"
SUMI = "#18181b"


@dataclass
class Palette:
    shu: str
    sashi: str

    @property
    def shu_text(self) -> str:
        return text_on(self.shu)

    @property
    def sashi_text(self) -> str:
        return text_on(self.sashi)


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def _rgb(hex_: str) -> tuple[float, float, float]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(hex_: str) -> float:
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(hex_)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(bg: str) -> str:
    """地の色に対して読める方（胡粉か墨）を返す。"""
    return GOFUN if contrast(bg, GOFUN) >= contrast(bg, SUMI) else SUMI


def _with_lightness(rgb, lightness: float, max_sat: float = 0.6) -> str:
    h, _, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb(h, lightness, min(s, max_sat))
    return _hex((r * 255, g * 255, b * 255))


def extract(path: Path) -> Palette:
    im = Image.open(path).convert("RGB")
    im.thumbnail((320, 320))
    px = list(im.getdata())

    # 顔料の画素：白すぎず黒すぎない。紙の地は暖色で彩度0.3前後なので、
    # 暖色は彩度0.42以上だけを取る。藍は退色して彩度が低いので寒色は0.15以上で取る
    bins: dict[int, list] = {}
    darks = []
    for r, g, b in px:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if l < 0.22:
            darks.append((r, g, b))
        hue = h * 360
        is_cool = 150 <= hue <= 290
        if 0.18 < l < 0.85 and (s > 0.42 or (is_cool and s > 0.15)):
            bins.setdefault(int(hue) // 20, []).append((r, g, b, hue))

    total = sum(len(v) for v in bins.values()) or 1
    clusters = []
    for k, v in bins.items():
        rgb = tuple(median(p[i] for p in v) for i in range(3))
        clusters.append((len(v) / total, k * 20 + 10, rgb))
    clusters.sort(reverse=True)

    cool = [c for c in clusters if 150 <= c[1] <= 290 and c[0] >= 0.05]
    warm = [c for c in clusters if (c[1] < 70 or c[1] > 320)]

    if cool:
        shu = _with_lightness(cool[0][2], 0.26)
    elif len(darks) > len(px) * 0.04:
        shu = _with_lightness(tuple(median(p[i] for p in darks) for i in range(3)), 0.16, max_sat=0.25)
    else:
        shu = SUMI

    sashi = _hex(warm[0][2]) if warm else _with_lightness(_rgb(shu), 0.45)
    return Palette(shu=shu, sashi=sashi)


def for_episode(ep, ep_dir: Path) -> Palette:
    """episode.yaml の palette 指定があればそれを、なければ最初の作品から取る。"""
    from .sources import asset_path

    auto = extract(asset_path(ep_dir, ep.artworks[0].key))
    override = getattr(ep, "palette", None) or {}
    return Palette(shu=override.get("shu", auto.shu), sashi=override.get("sashi", auto.sashi))
