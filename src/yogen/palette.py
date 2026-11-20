"""YŌGEN のカラーパレット：洋紅・紫・ベロ藍・藤黄・墨・胡粉の6色。

  sumi   墨      地
  yoko   洋紅    差し色（明治の化学染料の赤）
  mura   紫      差し色（明治の化学染料の紫）
  bero   ベロ藍  差し色（プルシアンブルー）
  too    藤黄    差し色。英字の題字の地
  gofun  胡粉    字幕の文字、墨の地の上の網点

地は墨、差し色は洋紅・紫・ベロ藍・藤黄から1〜3色をその回ごとに選ぶ（episode.yaml の colors）。
切り抜いた素材（stickers.py）には色を付けず、網点にして色面に重ねる。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Color:
    key: str
    name: str
    hex: str

    @property
    def rgb(self) -> tuple[int, int, int]:
        h = self.hex.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PALETTE: dict[str, Color] = {c.key: c for c in [
    Color("sumi", "墨", "#16130f"),
    Color("yoko", "洋紅", "#c8174f"),
    Color("mura", "紫", "#5d2a8c"),
    Color("bero", "ベロ藍", "#1f3d73"),
    Color("too", "藤黄", "#e8b326"),
    Color("gofun", "胡粉", "#eeefeb"),
]}
ACCENTS = ("yoko", "mura", "bero", "too")
DEFAULT = ["yoko"]
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
    """地の色の上で読める文字・網点の色（胡粉か墨）。"""
    white, sumi = PALETTE["gofun"].hex, PALETTE["sumi"].hex
    return white if contrast(bg, white) >= contrast(bg, sumi) else sumi
