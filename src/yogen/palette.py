"""YŌGEN のカラーパレット（混成）と、回ごとの5色の選び方。

パレットは浮世絵の顔料から作った13色。実測した「いまの色」と、画面で使う「混成の色」を持つ。
混成：面や地に使う落ち着いた色は褪せた実測の色のまま、目を引く差し色は刷りたての鮮やかさに戻す。

回ごとに使うのは5色だけ：墨（固定）＋ その回の浮世絵に多い顔料から4色。
作品の色は褪せているので、選ぶときは各顔料の実測の色と比べる。似た色同士（例：青2つ）は選ばない。
字幕の文字に使う胡粉の白は「紙」として、5色とは別に扱う。

回ごとに手で選ぶときは episode.yaml に colors: [bero, yoko, rokusho, ki] のように4色を書く。
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Pigment:
    key: str
    name: str
    hex: str        # 画面で使う色（混成）
    measured: str   # 浮世絵から実測した、いまの色（選ぶときの照合用）
    family: str     # 似た色を重ねないための系統


PALETTE: dict[str, Pigment] = {p.key: p for p in [
    Pigment("sumi", "墨", "#191c24", "#232b39", "black"),
    Pigment("bero", "ベロ藍", "#173a6e", "#20334e", "blue"),
    Pigment("ai", "藍（淡）", "#2f62a0", "#385c7e", "blue"),
    Pigment("ainezu", "藍鼠", "#6a8189", "#6a8189", "bluegray"),
    Pigment("beni", "紅", "#b8322a", "#9e4339", "red"),
    Pigment("tan", "丹", "#c95a2c", "#b26c4f", "red"),
    Pigment("hada", "肌", "#cfa584", "#cfa584", "skin"),
    Pigment("ki", "藤黄", "#e8b326", "#c3a672", "yellow"),
    Pigment("rokusho", "緑青", "#556d71", "#556d71", "green"),
    Pigment("nezumi", "鼠", "#7b7c68", "#7b7c68", "gray"),
    Pigment("yoko", "洋紅", "#c8174f", "#a8344f", "pink"),
    Pigment("mura", "紫", "#5d2a8c", "#5a3f6e", "purple"),
]}
GOFUN = "#f1efe8"   # 紙の白（字幕の文字）。5色とは別
FIXED = "sumi"
# 自動で選ぶのは鮮やかな差し色だけ。くすんだ色（藍鼠・肌・鼠）は手で選ぶときだけ使う
AUTO = ("bero", "ai", "beni", "tan", "ki", "rokusho", "yoko", "mura")
N_PICK = 4


def _rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0-255) → CIE Lab。形は (..., 3)。"""
    c = rgb / 255
    c = np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
    m = np.array([[.4124, .3576, .1805], [.2126, .7152, .0722], [.0193, .1192, .9505]], dtype=np.float32)
    xyz = c @ m.T / np.array([.95047, 1, 1.08883], dtype=np.float32)
    f = np.where(xyz > .008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def _is_paper(rgb: np.ndarray) -> np.ndarray:
    """紙の地（明るく色味の薄い黄土色）を除く。"""
    out = []
    for r, g, b in rgb / 255:
        _, l, s = colorsys.rgb_to_hls(r, g, b)
        out.append(l > .62 and s < .45)
    return np.array(out)


def scores(image: Image.Image) -> dict[str, float]:
    """各顔料が作品にどれだけ含まれるか（紙を除いた画素の中の割合に近い値）。"""
    im = image.convert("RGB")
    im.thumbnail((200, 200))
    px = np.asarray(im).reshape(-1, 3).astype(np.float32)
    px = px[~_is_paper(px)]
    if not len(px):
        return {k: 0.0 for k in PALETTE}
    lab = _lab(px)
    keys = list(PALETTE)
    refs = _lab(np.stack([_rgb(PALETTE[k].measured) for k in keys]))
    d = np.linalg.norm(lab[:, None, :] - refs[None], axis=2)
    nearest = d.argmin(1)
    close = d[np.arange(len(px)), nearest] < 28       # 遠すぎる画素はどの顔料にも数えない
    counts = np.bincount(nearest[close], minlength=len(keys)) / len(px)
    return dict(zip(keys, counts.tolist()))


def pick(image: Image.Image, n: int = N_PICK) -> list[str]:
    """墨＋作品に多い顔料 n 色。同じ系統は1つまで。"""
    sc = scores(image)
    chosen, fams = [FIXED], {PALETTE[FIXED].family}
    for k in sorted(sc, key=sc.get, reverse=True):
        if len(chosen) > n:
            break
        p = PALETTE[k]
        if k in chosen or p.family in fams or k not in AUTO:
            continue
        chosen.append(k)
        fams.add(p.family)
    # 作品に色が少ないとき（墨摺など）は、差し色を足して5色にする
    for k in ("ki", "yoko", "bero", "rokusho", "mura"):
        if len(chosen) > n:
            break
        if k not in chosen and PALETTE[k].family not in fams:
            chosen.append(k)
            fams.add(PALETTE[k].family)
    return chosen


def for_episode(ep, ep_dir: Path) -> list[Pigment]:
    """その回の5色。episode.yaml の colors（4色）があればそれを使う。"""
    from .sources import asset_path

    keys = [FIXED] + list(ep.colors) if getattr(ep, "colors", None) else pick(Image.open(asset_path(ep_dir, ep.artworks[0].key)))
    return [PALETTE[k] for k in keys]


def contrast(a: str, b: str) -> float:
    def lum(h):
        c = _rgb(h) / 255
        c = np.where(c <= .03928, c / 12.92, ((c + .055) / 1.055) ** 2.4)
        return float(.2126 * c[0] + .7152 * c[1] + .0722 * c[2])
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)


def text_on(bg: str) -> str:
    """地の色の上で読める文字の色（胡粉か墨）。"""
    sumi = PALETTE["sumi"].hex
    return GOFUN if contrast(bg, GOFUN) >= contrast(bg, sumi) else sumi
