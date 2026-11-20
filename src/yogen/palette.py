"""作品ごとの色を、その作品の顔料から取る。

  shu   主色   … 一文字ぼかしの帯と、版ズレ文字のずらす版に使う。
                 作品の上の方（空の側）で一番多い顔料。帯が作品の空の続きに見えるように
  sashi 差し色 … 題箋に使う。作品全体で、主色と違う色で一番多い顔料

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

# 色相の家（度）。赤は 0° をまたぐ
FAMILIES = {
    "red": (340, 15),
    "orange": (15, 40),
    "yellow": (40, 70),
    "green": (70, 150),
    "blue": (150, 260),
    "purple": (260, 340),
}
COOL = {"green", "blue", "purple"}


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


def _rgb(hex_: str) -> tuple[int, int, int]:
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


def tint(hex_: str, amount: float) -> str:
    """胡粉に色を amount だけ混ぜた淡い色（題箋の地など）。"""
    a, g = _rgb(hex_), _rgb(GOFUN)
    return _hex(tuple(g[i] + (a[i] - g[i]) * amount for i in range(3)))


def _with_lightness(rgb, lightness: float, max_sat: float = 0.6, min_sat: float = 0.0) -> str:
    h, _, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb(h, lightness, max(min_sat, min(s, max_sat)))
    return _hex((r * 255, g * 255, b * 255))


def _family(hue: float) -> str:
    for name, (lo, hi) in FAMILIES.items():
        if (lo <= hue < hi) if lo < hi else (hue >= lo or hue < hi):
            return name
    return "red"


def _pigments(pixels) -> dict[str, list]:
    """顔料の画素を色の家ごとに集める。

    紙の地は暖色で彩度0.3前後なので、暖色は彩度0.42以上だけを取る。
    藍は退色して彩度がかなり低い（空で0.1前後）ので、青・紫は0.07以上で取る。
    緑は退色した空や紙の灰色と区別しにくいので0.25以上。
    """
    fam: dict[str, list] = {}
    for r, g, b in pixels:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        name = _family(h * 360)
        if 0.18 < l < 0.85 and (s > 0.42 or (name in ("blue", "purple") and s > 0.07) or (name == "green" and s > 0.25)):
            fam.setdefault(name, []).append((r, g, b))
    return fam


def _core(pts, name: str) -> tuple[float, float, float]:
    """顔料の代表色。寒色は濃い方の半分（刷りの芯）、暖色は全体の中央値。"""
    if name in COOL:
        pts = sorted(pts, key=sum)[: max(1, len(pts) // 2)]
    return tuple(median(p[i] for p in pts) for i in range(3))


def _finish(name: str, rgb) -> str:
    # 寒色（退色した藍など）は帯の地として沈むよう少し濃くし、
    # 退色で灰色に寄った分の彩度を戻す（刷った当時の藍に寄せる）
    return _with_lightness(rgb, 0.27, min_sat=0.32) if name in COOL else _hex(rgb)


def extract(path: Path) -> Palette:
    im = Image.open(path).convert("RGB")
    im.thumbnail((320, 320))
    w, h = im.size
    data = list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())

    whole = _pigments(data)
    if not whole:
        return Palette(shu=SUMI, sashi=SUMI)

    # 上の方（題字の下〜画面の45%）＝空の側
    top = _pigments(data[int(h * 0.08) * w: int(h * 0.45) * w])
    top_rank = sorted(top.items(), key=lambda kv: len(kv[1]), reverse=True)
    shu_name = top_rank[0][0] if top_rank and len(top_rank[0][1]) > 40 else max(whole, key=lambda k: len(whole[k]))
    shu = _finish(shu_name, _core(top.get(shu_name) or whole[shu_name], shu_name))

    rest = sorted(((k, v) for k, v in whole.items() if k != shu_name), key=lambda kv: len(kv[1]), reverse=True)
    sashi = _hex(_core(rest[0][1], rest[0][0])) if rest else _with_lightness(_rgb(shu), 0.4)
    return Palette(shu=shu, sashi=sashi)


def for_episode(ep, ep_dir: Path) -> Palette:
    """episode.yaml の palette 指定があればそれを、なければ最初の作品から取る。"""
    from .sources import asset_path

    auto = extract(asset_path(ep_dir, ep.artworks[0].key))
    override = ep.palette or {}
    return Palette(shu=override.get("shu", auto.shu), sashi=override.get("sashi", auto.sashi))
