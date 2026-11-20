"""英字の質感（スクリーンプリント・スプレー缶）と、コピー機の汚れ。動画用（Pillow + numpy）。

  screen_print  インクのにじみで角が丸く、乗りにむら、細かいかすれ
  spray         輪郭の外に霧の粒、字の下端から数本の垂れ
  xerox_grain   紙のざらつき、トナーの粒、縁の焼け、こすれの筋
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ROOT

FONTS = ROOT / "assets" / "fonts"
WIDE_BLACK = FONTS / "archivo" / "Archivo-ExpandedBlack.ttf"
WIDE_BOLD = FONTS / "archivo" / "Archivo-SemiExpandedBold.ttf"
SEMIBOLD = FONTS / "archivo" / "Archivo-SemiBold.ttf"
STENCIL = FONTS / "bigshoulders" / "BigShouldersStencilDisplay-Black.ttf"


def text_mask(text: str, font_path: Path, size: int, align: str = "center", spacing: float = .0) -> Image.Image:
    """文字の形のマスク（L）。改行で複数行。"""
    font = ImageFont.truetype(str(font_path), size)
    lines = text.split("\n")
    boxes = [font.getbbox(l) for l in lines]
    lh = int(size * (1 + spacing))
    w = max(b[2] - b[0] for b in boxes) + size // 2
    h = lh * len(lines) + size // 2
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for i, (l, b) in enumerate(zip(lines, boxes)):
        lw = b[2] - b[0]
        x = (w - lw) // 2 - b[0] if align == "center" else size // 4 - b[0]
        d.text((x, size // 4 + i * lh), l, font=font, fill=255)
    return m.crop(m.getbbox())


def _noise(shape, scale: float, rng) -> np.ndarray:
    """0〜1 の滑らかなノイズ。scale は粒の大きさ（px）。"""
    h, w = shape
    sh, sw = max(2, int(h / scale) + 2), max(2, int(w / scale) + 2)
    small = Image.fromarray((rng.random((sh, sw)) * 255).astype(np.uint8))
    return np.asarray(small.resize((w, h), Image.BICUBIC)).astype(np.float32) / 255


def _pad(m: Image.Image, p: int) -> Image.Image:
    out = Image.new("L", (m.width + p * 2, m.height + p * 2), 0)
    out.paste(m, (p, p))
    return out


def screen_print(mask: Image.Image, color, seed: int = 4, spread: float = 1.0) -> Image.Image:
    rng = np.random.default_rng(seed)
    p = int(6 * spread) + 2
    m = _pad(mask, p)
    # にじみ：少し太らせてぼかし、しきい値で角を丸める
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.6 * spread))
    a = np.asarray(m).astype(np.float32) / 255
    a = np.clip((a - .42) * 6, 0, 1)
    # インクの乗りのむら（大きな斑）と、細かいかすれ
    patch = _noise(a.shape, 60 * spread, rng)
    fine = rng.random(a.shape)
    a = a * np.clip(.62 + patch * .6, 0, 1) * (fine > .07)
    out = Image.new("RGBA", m.size, (*color, 0))
    out.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
    return out


def spray(mask: Image.Image, color, seed: int = 2, scale: float = 1.0, drips: float = 1.0) -> Image.Image:
    """スプレー缶：霧の粒（輪郭のすぐ外に濃く、外へ薄く）と、下への垂れ。scale は字の太さに合わせる。"""
    rng = np.random.default_rng(seed)
    r = random.Random(seed)
    p = int(40 * scale) + 4
    m = _pad(mask, p)
    core = np.asarray(m.filter(ImageFilter.GaussianBlur(.7))).astype(np.float32) / 255
    near = np.asarray(m.filter(ImageFilter.GaussianBlur(3.5 * scale))).astype(np.float32) / 255
    far = np.asarray(m.filter(ImageFilter.GaussianBlur(14 * scale))).astype(np.float32) / 255
    n = rng.random(core.shape)
    speck = ((near * 1.3 - n) > 0) | ((far * .9 - n) > 0)
    a = np.maximum(core, speck.astype(np.float32) * .95)
    img = Image.fromarray((a * 255).astype(np.uint8))
    # 垂れ：字の下端から、ところどころ縦にインクが流れる
    d = ImageDraw.Draw(img)
    arr = np.asarray(m) > 128
    h, w = arr.shape
    step = max(6, int(14 * scale))
    for x in range(0, w, step):
        if r.random() > .38 * drips:
            continue
        col = np.nonzero(arr[:, x])[0]
        if not len(col):
            continue
        y0 = col.max()
        length = int(r.expovariate(1 / (34 * scale)))
        width = max(2, int(r.uniform(2.2, 5.5) * scale))
        if length < 6:
            continue
        d.line((x, y0 - 2, x, y0 + length), fill=255, width=width)
        d.ellipse((x - width * .75, y0 + length - width * .75, x + width * .75, y0 + length + width * .75), fill=255)
    out = Image.new("RGBA", img.size, (*color, 0))
    out.putalpha(img)
    return out


def spray_stroke(size, paths, color, width: int = 14, seed: int = 5, scale: float = 1.0) -> Image.Image:
    """スプレーで描いた線（丸・矢印など）。paths は点列のリスト。"""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for pts in paths:
        d.line(pts, fill=255, width=width, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=255)
    return spray(m, color, seed=seed, scale=scale, drips=.5)


def xerox_grain(size, seed: int = 9, strength: float = 1.0) -> Image.Image:
    """画面全体に重ねる汚れ（RGBA）。"""
    rng = np.random.default_rng(seed)
    w, h = size
    grain = rng.normal(0, 1, (h, w)).astype(np.float32)
    dark = np.clip(-grain * 18 * strength, 0, 60)
    # トナーの粒：明るい点
    # まばらに、ところどころ固まって出る
    clump = _noise((h, w), 140, rng)
    toner = (rng.random((h, w)) > .9993 - np.clip(clump - .7, 0, 1) * .006).astype(np.float32)
    toner = np.asarray(Image.fromarray((toner * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))).astype(np.float32) / 255
    # 縁の焼け
    yy, xx = np.mgrid[0:h, 0:w]
    vign = np.clip(((xx / w - .5) ** 2 * 1.6 + (yy / h - .46) ** 2 * 1.1) * 2.6 - .35, 0, 1) * 170 * strength
    # こすれの筋
    streak = np.zeros((h, w), np.float32)
    r = random.Random(seed)
    for _ in range(3):
        y = r.randint(0, h - 1)
        th = r.randint(2, 7)
        streak[y:y + th, :] = r.uniform(30, 70) * strength
    alpha = np.clip(dark + vign + streak, 0, 255)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., 3] = alpha.astype(np.uint8)
    layer = Image.fromarray(out, "RGBA")
    light = np.zeros((h, w, 4), np.uint8)
    light[..., :3] = 225
    light[..., 3] = (toner * 120).astype(np.uint8)
    layer.alpha_composite(Image.fromarray(light, "RGBA"))
    return layer
