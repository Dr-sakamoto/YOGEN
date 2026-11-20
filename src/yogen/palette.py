"""YŌGEN のカラーパレット（毒々しい色）。

浮世絵の色には合わせない。地は墨で、差し色は1〜3色をその回ごとに選ぶ（作品の色とは無関係）。
主役の作品だけ原画の色で見せ、背景や脇の紙片は差し色の2色刷りにして画面の大半を塗る。

  sumi    墨        地
  pink    毒ピンク  一番の主役
  green   毒緑
  blue    電気青
  purple  毒紫
  yellow  毒黄      英字の題字の地だけ
  white   紙        字幕の文字

回ごとの差し色は episode.yaml の colors: [pink] や [green, purple] で選ぶ。書かなければ DEFAULT。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Color:
    key: str
    name: str
    hex: str


PALETTE: dict[str, Color] = {c.key: c for c in [
    Color("sumi", "墨", "#0d0d10"),
    Color("pink", "毒ピンク", "#ff1f8e"),
    Color("green", "毒緑", "#2ee86a"),
    Color("blue", "電気青", "#2338ff"),
    Color("purple", "毒紫", "#8c1fe0"),
    Color("yellow", "毒黄", "#ffd60a"),
    Color("white", "紙", "#f4f2ec"),
]}
ACCENTS = ("pink", "green", "blue", "purple")
DEFAULT = ["pink"]
MAX_ACCENTS = 3


def for_episode(ep) -> list[Color]:
    """その回の色：墨＋差し色1〜3色。"""
    keys = list(getattr(ep, "colors", None) or DEFAULT)
    bad = [k for k in keys if k not in ACCENTS]
    if bad or not 1 <= len(keys) <= MAX_ACCENTS:
        raise ValueError(f"colors は {ACCENTS} から1〜{MAX_ACCENTS}色: {keys}")
    return [PALETTE["sumi"]] + [PALETTE[k] for k in keys]


def _rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def contrast(a: str, b: str) -> float:
    def lum(h):
        c = _rgb(h) / 255
        c = np.where(c <= .03928, c / 12.92, ((c + .055) / 1.055) ** 2.4)
        return float(.2126 * c[0] + .7152 * c[1] + .0722 * c[2])
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)


def text_on(bg: str) -> str:
    """地の色の上で読める文字の色（紙の白か墨）。"""
    white, sumi = PALETTE["white"].hex, PALETTE["sumi"].hex
    return white if contrast(bg, white) >= contrast(bg, sumi) else sumi
