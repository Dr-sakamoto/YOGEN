"""架空の雑誌表紙のコラージュ生成。秩序（スイス式のグリッド）と無秩序（パンク・コロコロ式の過剰）を衝突させる。

固定のテンプレートは持たない。seed から「遺伝子」（Genome）を引き、そこから
  参照6系統の配合比 → 領域の分割（グリッド上で再帰分割）→ 各領域の中身 → 秩序の破壊 → 雑誌の意匠
を毎回変える。作った後に、美的完成度（aesthetic）と新規性（novelty）を別々に採点する。

  generate(n, keep, out_dir)   n 枚作り、完成度が基準以上のものから新規性が高い順に keep 枚残す

素材は materials/index.yaml のパブリックドメインの図版と stickers.yaml の切り抜きだけ。
作った表紙の特徴量は out_dir/history.json に積み、次回以降の新規性の判定に使う。
"""
from __future__ import annotations

import colorsys
import json
import math
import random
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import brand
from .inkfx import (SEMIBOLD, STENCIL, WIDE_BLACK, WIDE_BOLD, FONTS, screen_print, text_mask,
                    xerox_grain)
from .materials import load_index, open_material, torn
from .palette import ACCENTS, PALETTE, text_on
from .stickers import _base, halftone_sticker, recipes

W, H = 1200, 1600
REFS = ("punk", "korokoro", "ukiyoe", "comic", "swiss", "british")

DISPLAY_FONTS = [
    WIDE_BLACK, WIDE_BOLD, SEMIBOLD, STENCIL,
    FONTS / "contrast" / "Bricolage-CondExtraBold.ttf",
    FONTS / "contrast" / "Fraunces-BlackSoft.ttf",
    FONTS / "contrast" / "Shrikhand.ttf",
    FONTS / "rounded" / "Rubik-Black.ttf",
    FONTS / "archivo" / "Archivo-Black.ttf",
]
# 実在の事実を主張しない、雰囲気だけのコピー（台本とは別。事実は episode.yaml からだけ取る）
HEADLINES = [
    "PHANTOMS OF THE\nFLOATING WORLD", "THE LANTERN ISSUE", "WHO IS WATCHING\nTHE FOX?", "CUT. PASTE.\nHAUNT.",
    "GHOSTS IN\nTHE GRID", "DO NOT LOOK\nAT THE CAT", "BONES / INK / NOISE", "SPECIAL:\nTHE SKELETON DRUM",
    "EDO\nUNDERGROUND", "NIGHT PARADE\n100 DEMONS", "PRINTED\nUNDER THE MOON", "MASK OFF",
    "THE GOLDFISH\nKNOWS", "WARNING:\nWOODBLOCK", "SOUND OF\nLANTERNS", "FLOAT.\nFADE.\nREPEAT.",
]
KICKERS = ["INSIDE!", "FREE POSTER", "VOL. 1", "NEW", "LIMITED", "SPOOK ZINE", "TOXIC INK", "EXTRA", "DOUBLE ISSUE", "SIDE B"]


# ---------- 遺伝子 ----------

@dataclass
class Genome:
    seed: int
    mix: dict                      # 参照6系統の配合比（合計1）
    accents: list                  # 差し色 1〜3
    cols: int                      # グリッドの列数
    gutter: int
    splits: int                    # 領域の分割回数
    masthead: str                  # top / bottom / side / giant
    hero: str                      # 主役の素材キー
    hero_zoom: float
    disorder: float                # 秩序を壊す強さ 0〜1
    density: float                 # 散らす小物の量 0〜1
    fonts: list = field(default_factory=list)
    issue: int = 1
    price: str = ""
    layout: str = ""               # 分割の癖（記録用）


def _dirichlet(rng: np.random.Generator) -> dict:
    # 集中度を毎回変える：ほぼ単色の回も、均等に混ざる回も出る
    conc = float(rng.choice([.35, .6, 1.0, 2.5]))
    v = rng.dirichlet([conc] * len(REFS))
    return {k: float(x) for k, x in zip(REFS, v)}


def heroes() -> list[str]:
    ok = []
    for k, v in load_index().items():
        if v.get("kind") in ("print", "ink") and (Path(__file__).resolve().parents[2] / "materials" / f"{k}.jpg").exists():
            ok.append(k)
    return ok


def sample_genome(seed: int) -> Genome:
    rng = np.random.default_rng(seed)
    n_acc = int(rng.choice([1, 2, 3], p=[.25, .5, .25]))
    mix = _dirichlet(rng)
    hs = heroes()
    return Genome(
        seed=seed, mix=mix,
        accents=[str(a) for a in rng.choice(ACCENTS, n_acc, replace=False)],
        cols=int(rng.choice([4, 5, 6, 8, 12])),
        gutter=int(rng.choice([0, 6, 12, 20])),
        splits=int(rng.integers(5, 12)),
        masthead=str(rng.choice(["top", "bottom", "side", "giant"], p=[.4, .15, .2, .25])),
        hero=str(rng.choice(hs)),
        hero_zoom=float(rng.choice([1.0, 1.6, 2.5, 4.0])),
        disorder=float(np.clip(.25 + mix["punk"] * .7 + mix["british"] * .4 + rng.normal(0, .12), .1, 1)),
        density=float(np.clip(.35 + mix["korokoro"] * .9 + rng.normal(0, .1), .2, 1)),
        fonts=[str(i) for i in rng.choice(len(DISPLAY_FONTS), 3, replace=False)],
        issue=int(rng.integers(1, 99)),
        price=str(rng.choice(["¥380", "$4.99", "£3.50", "€5.00", "¥1,000", "FREE"])),
    )


# ---------- 部品 ----------

def _font(g: Genome, i: int) -> Path:
    return DISPLAY_FONTS[int(g.fonts[i % len(g.fonts)])]


def _rgb(key: str):
    return PALETTE[key].rgb


def cover(img: Image.Image, w: int, h: int, zoom: float, rng: random.Random) -> Image.Image:
    """領域いっぱいに切り出す。zoom>1 でさらに寄る（極端な拡大）。"""
    s = max(w / img.width, h / img.height) * zoom
    im = img.resize((max(w, int(img.width * s)), max(h, int(img.height * s))), Image.LANCZOS)
    x = rng.randint(0, im.width - w)
    y = rng.randint(0, im.height - h)
    return im.crop((x, y, x + w, y + h))


def barcode(w: int, h: int, rng: random.Random, fg, bg) -> Image.Image:
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    x = w * .06
    while x < w * .94:
        bw = rng.choice([2, 2, 3, 5, 7])
        d.rectangle((x, h * .08, x + bw, h * .78), fill=fg)
        x += bw + rng.choice([2, 3, 4, 6])
    f = ImageFont.truetype(str(SEMIBOLD), max(8, h // 8))
    d.text((w * .06, h * .8), " ".join(str(rng.randint(10, 99)) for _ in range(5)), font=f, fill=fg)
    return im.convert("RGBA")


def burst(size: int, color, rng: random.Random, spikes: int | None = None) -> Image.Image:
    spikes = spikes or rng.randint(10, 22)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    pts = []
    for i in range(spikes * 2):
        a = math.pi * i / spikes + rng.uniform(-.05, .05)
        r = c * (1 if i % 2 == 0 else rng.uniform(.62, .85))
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=(*color, 255))
    return im


def text_layer(text: str, font: Path, size: int, color, rng: random.Random, style: str = "flat") -> Image.Image:
    m = text_mask(text, font, size, align="left" if rng.random() < .5 else "center", spacing=-.12)
    if style == "print":
        return screen_print(m, color, seed=rng.randint(1, 999))
    lay = Image.new("RGBA", m.size, (*color, 0))
    lay.putalpha(m)
    return lay


def rot(layer: Image.Image, angle: float) -> Image.Image:
    return layer.rotate(angle, resample=Image.BICUBIC, expand=True) if angle else layer


@lru_cache(maxsize=256)
def _ht(key: str, idx: int, ink, invert: bool, width: int) -> Image.Image:
    return halftone_sticker(key, idx, ink=ink, cell=max(5, width // 55), width=width, invert=invert)


@lru_cache(maxsize=32)
def _hero(key: str) -> Image.Image:
    im = open_material(key)
    im.thumbnail((2000, 2400))
    return im


# ---------- 組み立て ----------

class Cover:
    """描画と同時に、どこに何を置いたか（trace）を記録する。採点はこの記録と画像から行う。"""

    def __init__(self, g: Genome):
        self.g = g
        self.r = random.Random(g.seed)
        self.canvas = Image.new("RGBA", (W, H), (*_rgb("sumi"), 255))
        self.trace: list[dict] = []
        self.colors = [_rgb(a) for a in g.accents]

    # 記録つきの貼り付け
    def put(self, layer: Image.Image, xy, kind: str, angle: float = 0, shadow: float = 0, on_grid: bool = False):
        layer = rot(layer, angle)
        if shadow:
            sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            sh.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * shadow)))
            self.canvas.alpha_composite(sh, (int(xy[0]) + 7, int(xy[1]) + 10)) if xy[0] >= 0 and xy[1] >= 0 else \
                self.canvas.paste(sh, (int(xy[0]) + 7, int(xy[1]) + 10), sh)
        x, y = int(xy[0]), int(xy[1])
        if x >= 0 and y >= 0 and x + layer.width <= W and y + layer.height <= H:
            self.canvas.alpha_composite(layer, (x, y))
        else:
            self.canvas.paste(layer, (x, y), layer)
        self.trace.append(dict(kind=kind, box=(x, y, x + layer.width, y + layer.height), angle=angle, on_grid=on_grid))

    # --- グリッドと領域 ---
    def grid_lines(self):
        g = self.g
        m = 40
        xs = [m + (W - 2 * m) * i / g.cols for i in range(g.cols + 1)]
        ys = [m + (H - 2 * m) * i / (g.cols * 4 // 3) for i in range(g.cols * 4 // 3 + 1)]
        return xs, ys

    def regions(self) -> list[tuple[int, int, int, int]]:
        g, r = self.g, self.r
        xs, ys = self.grid_lines()
        rects = [(xs[0], ys[0], xs[-1], ys[-1])]
        bias = r.choice(["balanced", "vertical", "horizontal", "big-small"])
        g.layout = bias
        for _ in range(g.splits):
            areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in rects]
            i = r.choices(range(len(rects)), weights=[a ** (1.6 if bias == "big-small" else 1.0) for a in areas])[0]
            x0, y0, x1, y1 = rects.pop(i)
            vert = (x1 - x0) > (y1 - y0) if bias == "balanced" else \
                (bias == "vertical" if r.random() < .75 else bias != "vertical")
            if vert:
                cuts = [x for x in xs if x0 + 120 < x < x1 - 120]
                if not cuts:
                    rects.append((x0, y0, x1, y1)); continue
                c = r.choice(cuts)
                rects += [(x0, y0, c, y1), (c, y0, x1, y1)]
            else:
                cuts = [y for y in ys if y0 + 120 < y < y1 - 120]
                if not cuts:
                    rects.append((x0, y0, x1, y1)); continue
                c = r.choice(cuts)
                rects += [(x0, y0, x1, c), (x0, c, x1, y1)]
        gt = g.gutter
        return [(int(a + gt / 2), int(b + gt / 2), int(c - gt / 2), int(d - gt / 2)) for a, b, c, d in rects]

    # --- 領域の中身 ---
    def kinds(self, rects):
        """領域ごとの中身を、配合比から引く。最大の領域は主役の作品。"""
        mix, r = self.g.mix, self.r
        order = sorted(range(len(rects)), key=lambda i: -(rects[i][2] - rects[i][0]) * (rects[i][3] - rects[i][1]))
        w = {
            "hero": .5 + mix["ukiyoe"] * 2,
            "panel": .6 + mix["comic"] * 1.5 + mix["punk"],
            "type": .4 + mix["swiss"] * 2 + mix["british"],
            "strip": .2 + mix["punk"] * 1.5,
            "pattern": .2 + mix["ukiyoe"] + mix["korokoro"],
            "photocopy": .2 + mix["punk"] * 1.5 + mix["british"],
        }
        out = {order[0]: "hero"}
        for i in order[1:]:
            out[i] = r.choices(list(w), weights=list(w.values()))[0]
        return out

    def fill(self, rect, kind: str):
        g, r = self.g, self.r
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        if w < 30 or h < 30:
            return
        col = r.choice(self.colors)
        if kind == "hero":
            im = cover(_hero(g.hero), w, h, g.hero_zoom if (w * h > W * H * .12) else 1.0, r)
            if r.random() < .25:
                im = ImageOps.autocontrast(ImageOps.grayscale(im)).convert("RGB")
                im = ImageChops.multiply(im, Image.new("RGB", im.size, col))  # 一色刷りに染める
            self.put(im.convert("RGBA"), (x0, y0), "hero", on_grid=True)
        elif kind == "panel":
            self.put(Image.new("RGBA", (w, h), (*col, 255)), (x0, y0), "panel", on_grid=True)
            ink = text_on("#%02x%02x%02x" % col)
            ink_rgb = _rgb("sumi") if ink == PALETTE["sumi"].hex else _rgb("gofun")
            key = r.choice(list(recipes()))
            s = _ht(key, r.randrange(len(recipes()[key])), ink_rgb, ink_rgb != _rgb("sumi"), 600)
            k = min(w * 1.1 / s.width, h * 1.1 / s.height) * r.choice([.7, 1.0, 1.6])
            s = s.resize((max(1, int(s.width * k)), max(1, int(s.height * k))), Image.LANCZOS)
            clip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            clip.alpha_composite(s, (r.randint(-s.width // 4, max(0, w - s.width * 3 // 4)),
                                     r.randint(-s.height // 4, max(0, h - s.height * 3 // 4))))
            self.put(clip, (x0, y0), "sticker", on_grid=True)
        elif kind == "type":
            bg = r.choice([_rgb("gofun"), _rgb("sumi"), col])
            fg = _rgb("sumi") if bg != _rgb("sumi") and text_on("#%02x%02x%02x" % bg) == PALETTE["sumi"].hex else _rgb("gofun")
            self.put(Image.new("RGBA", (w, h), (*bg, 255)), (x0, y0), "panel", on_grid=True)
            txt = r.choice(HEADLINES)
            lay = text_layer(txt, DISPLAY_FONTS[int(g.fonts[r.randrange(3)])], 200, fg, r, "print" if r.random() < g.disorder else "flat")
            k = min(w * .9 / lay.width, h * .86 / lay.height)
            lay = lay.resize((max(1, int(lay.width * k)), max(1, int(lay.height * k))), Image.LANCZOS)
            self.put(lay, (x0 + (w - lay.width) // 2, y0 + (h - lay.height) // 2), "text", on_grid=True)
        elif kind == "strip":
            im = cover(_hero(r.choice(heroes())), w, h, r.choice([1.0, 2.0]), r).convert("RGB")
            n = r.randint(3, 8)
            out = im.copy()
            for i in range(n):  # 帯に切って、ずらして貼り直す
                if w >= h:
                    a, b = int(w * i / n), int(w * (i + 1) / n)
                    out.paste(im.crop((a, 0, b, h)), (a, int(r.gauss(0, h * .12 * (.4 + g.disorder)))))
                else:
                    a, b = int(h * i / n), int(h * (i + 1) / n)
                    out.paste(im.crop((0, a, w, b)), (int(r.gauss(0, w * .12 * (.4 + g.disorder))), a))
            self.put(out.convert("RGBA"), (x0, y0), "strip", on_grid=True)
        elif kind == "pattern":
            key = r.choice(list(recipes()))
            bg = r.choice([_rgb("sumi"), col])
            ink = _rgb("gofun") if bg == _rgb("sumi") else _rgb("sumi")
            tile = _ht(key, 0, ink, bg == _rgb("sumi"), 300)
            cell = r.choice([90, 130, 190])
            tile = tile.resize((cell, int(tile.height * cell / tile.width)), Image.LANCZOS)
            im = Image.new("RGBA", (w, h), (*bg, 255))
            for j, y in enumerate(range(-tile.height // 2, h, int(tile.height * 1.05))):
                for x in range(-cell, w, int(cell * 1.1)):
                    im.alpha_composite(tile, (x + (cell // 2 if j % 2 else 0), y)) if x >= 0 and y >= 0 else \
                        im.paste(tile, (x + (cell // 2 if j % 2 else 0), y), tile)
            self.put(im, (x0, y0), "pattern", on_grid=True)
        else:  # photocopy：作品をコピー機にかけた白黒を色の地に
            im = cover(_hero(r.choice(heroes())), w, h, r.choice([1.0, 1.6, 2.5]), r)
            g_ = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=2)
            thr = r.uniform(90, 150)
            m = g_.point(lambda v: 255 if v < thr else 0).filter(ImageFilter.MedianFilter(3))
            base = Image.new("RGBA", (w, h), (*col, 255))
            ink = Image.new("RGBA", (w, h), (*_rgb("sumi"), 255))
            ink.putalpha(m)
            base.alpha_composite(ink)
            self.put(base, (x0, y0), "photocopy", on_grid=True)

    # --- 雑誌の意匠 ---
    def masthead(self):
        g, r = self.g, self.r
        mark = brand.wordmark(brand.SUMI)
        side = g.masthead == "side"
        k_w = {"top": .78, "bottom": .62, "side": .0, "giant": 1.35}[g.masthead]
        if side:
            mark = rot(mark, 90)
            tw = int(W * .18)
            lay = mark.resize((tw, int(mark.height * tw / mark.width)), Image.LANCZOS)
            xy = (r.choice([20, W - lay.width - 20]), r.randint(40, 120))
            plate = Image.new("RGBA", (lay.width + 40, lay.height + 40), (*brand.TOO, 255))
            plate.alpha_composite(lay, (20, 20))
            self.put(plate, (xy[0] - 20, xy[1] - 20), "masthead", shadow=.5)
            return
        tw = int(W * k_w)
        lay = mark.resize((tw, int(mark.height * tw / mark.width)), Image.LANCZOS)
        plate = Image.new("RGBA", (lay.width + 70, lay.height + 50), (*brand.TOO, 255))
        plate.alpha_composite(lay, (35, 25))
        y = {"top": 28, "bottom": H - plate.height - 28, "giant": r.randint(-plate.height // 6, 40)}[g.masthead]
        x = r.choice([28, (W - plate.width) // 2, W - plate.width - 28]) if g.masthead != "giant" else -int(plate.width * .08)
        self.put(plate, (x, y), "masthead", angle=r.uniform(-2, 2) * g.disorder, shadow=.55)

    def furniture(self):
        g, r = self.g, self.r
        gofun, sumi = _rgb("gofun"), _rgb("sumi")
        # バーコード（隅）
        bw = r.randint(170, 240)
        bc = barcode(bw, int(bw * .55), r, sumi, gofun)
        corner = r.choice([(W - bw - 30, H - bc.height - 30), (30, H - bc.height - 30)])
        if g.masthead == "bottom":
            corner = (corner[0], 330)
        self.put(bc, corner, "barcode", angle=r.uniform(-4, 4) * g.disorder, shadow=.4)
        # 号数と値段
        lab = text_layer(f"No.{g.issue:02d}  {g.price}", WIDE_BLACK, 70, gofun, r)
        lab = lab.resize((int(lab.width * 260 / lab.width), int(lab.height * 260 / lab.width)), Image.LANCZOS)
        plate = Image.new("RGBA", (lab.width + 24, lab.height + 20), (*sumi, 255))
        plate.alpha_composite(lab, (12, 10))
        self.put(plate, (r.randint(30, W - 300), r.choice([22 + 220, H // 2 + r.randint(-80, 80)])), "label", angle=r.uniform(-8, 8) * g.disorder, shadow=.4)
        # 顔アイコン（アメコミの表紙の隅の丸）
        if r.random() < .35 + g.mix["comic"]:
            d = r.randint(150, 230)
            face = r.choice(["oni", "neko", "kitsune", "dokuro", "daruma"])
            col = r.choice(self.colors)
            ring = Image.new("RGBA", (d, d), (0, 0, 0, 0))
            dr = ImageDraw.Draw(ring)
            dr.ellipse((0, 0, d - 1, d - 1), fill=(*sumi, 255))
            dr.ellipse((8, 8, d - 9, d - 9), fill=(*col, 255))
            s = _ht(face, 0, sumi, False, 400)
            k = (d * .78) / max(s.size)
            s = s.resize((int(s.width * k), int(s.height * k)), Image.LANCZOS)
            ring.alpha_composite(s, ((d - s.width) // 2, (d - s.height) // 2))
            self.put(ring, (r.randint(30, W - d - 30), r.randint(H // 3, H - d - 60)), "face", angle=r.uniform(-12, 12) * g.disorder, shadow=.5)
        # 爆発の吹き出し＋見出しの断片
        if r.random() < .3 + g.mix["comic"] + g.mix["korokoro"] * .5:
            size = r.randint(240, 380)
            col = r.choice(self.colors + [brand.TOO])
            b = burst(size, col, r)
            word = r.choice(KICKERS)
            t = text_layer(word, DISPLAY_FONTS[int(g.fonts[1])], 120, sumi if text_on("#%02x%02x%02x" % col) == PALETTE["sumi"].hex else gofun, r)
            k = size * .62 / t.width
            t = t.resize((int(t.width * k), int(t.height * k)), Image.LANCZOS)
            b.alpha_composite(t, ((size - t.width) // 2, (size - t.height) // 2))
            self.put(b, (r.randint(0, W - size), r.randint(H // 5, H - size - 80)), "burst", angle=r.uniform(-18, 18), shadow=.45)

    def scatter(self):
        """小物を過剰に撒く（コロコロ・パンク）。大きさの差を極端に。"""
        g, r = self.g, self.r
        n = int(6 + g.density * 26)
        for _ in range(n):
            key = r.choice(list(recipes()))
            on_dark = r.random() < .5
            ink = _rgb("gofun") if on_dark else _rgb("sumi")
            s = _ht(key, 0, ink, on_dark, 360)
            size = int(r.choice([60, 90, 140, 220, 340, 560]) * (.7 + g.disorder * .6))
            s = s.resize((size, max(1, int(s.height * size / s.width))), Image.LANCZOS)
            self.put(s, (r.randint(-size // 3, W - size * 2 // 3), r.randint(-size // 3, H - size * 2 // 3)), "scatter",
                     angle=r.uniform(-40, 40) * g.disorder)
        # 紙片（原画の色のまま）：ちぎった作品の切れ端を斜めに
        for _ in range(r.randint(1, 3 + int(g.mix["punk"] * 4))):
            im = cover(_hero(r.choice(heroes())), r.randint(180, 420), r.randint(120, 360), r.choice([1.0, 2.2]), r)
            piece = torn(im, amp=r.randint(6, 18), seed=r.randint(1, 99), paper=_rgb("gofun"), paper_w=r.randint(4, 10))
            self.put(piece, (r.randint(0, W - piece.width), r.randint(0, H - piece.height)), "scrap",
                     angle=r.uniform(-25, 25) * (.4 + g.disorder), shadow=.5)

    def swiss(self):
        """秩序の側：細い罫線・大きな数字・小さな固い文字。グリッドの線に揃える。"""
        g, r = self.g, self.r
        xs, ys = self.grid_lines()
        gofun = _rgb("gofun")
        d = ImageDraw.Draw(self.canvas)
        for _ in range(int(2 + g.mix["swiss"] * 8)):
            if r.random() < .5:
                x = r.choice(xs)
                d.line((x, 0, x, H), fill=(*gofun, 255), width=r.choice([1, 2, 4]))
            else:
                y = r.choice(ys)
                d.line((0, y, W, y), fill=(*gofun, 255), width=r.choice([1, 2, 4]))
        if g.mix["swiss"] > .15 or r.random() < .5:
            big = text_layer(str(g.issue), WIDE_BLACK, 400, r.choice([_rgb("gofun"), *self.colors]), r)
            k = r.choice([.18, .3, .5]) * W / big.width
            big = big.resize((int(big.width * k), int(big.height * k)), Image.LANCZOS)
            x = r.choice(xs[:-1])
            self.put(big, (x, r.choice(ys[:-3])), "numeral", on_grid=True)
        # 小さな固い組み：グリッドに揃えた段落の代わりの文字列
        small = "\n".join(r.choice(["WOODBLOCK / PRINT / GHOST", "VOL.1 — NIGHT EDITION", "ALL MATERIALS PUBLIC DOMAIN",
                                    "EDO 1603–1868 / NOT AN OFFICIAL ARCHIVE", "A GUIDE TO THE UNSEEN"]) for _ in range(3))
        t = text_layer(small, SEMIBOLD, 40, gofun, r)
        t = t.resize((int(t.width * 330 / t.width), int(t.height * 330 / t.width)), Image.LANCZOS)
        self.put(t, (r.choice(xs[:-2]), r.choice(ys[1:-2]) + 6), "smalltext", on_grid=True)

    def headline(self):
        """特集見出し：大きく、ときに縦、ときに切れるほど。ドイツ・スイス式と英国式で置き方を変える。"""
        g, r = self.g, self.r
        col = r.choice([_rgb("gofun"), brand.TOO, *self.colors])
        lay = text_layer(r.choice(HEADLINES), DISPLAY_FONTS[int(g.fonts[0])], 260, col, r, "print")
        k = r.choice([.45, .6, .85]) * W / lay.width
        lay = lay.resize((int(lay.width * k), int(lay.height * k)), Image.LANCZOS)
        angle = 90 if (r.random() < g.mix["british"] + .1) else r.uniform(-6, 6) * g.disorder
        if angle == 90:
            lay = rot(lay, 90)
            angle = 0
        xs, ys = self.grid_lines()
        snap = r.random() > g.disorder * .5
        x = min(r.choice(xs), W - lay.width // 2) if snap else r.randint(-lay.width // 5, W - lay.width * 4 // 5)
        y = r.choice(ys[2:-2]) if snap else r.randint(H // 6, H * 4 // 5)
        self.put(lay, (x, y), "headline", angle=angle, shadow=.55, on_grid=snap)

    def destroy_order(self):
        """秩序を部分的に壊す：斜めの断ち切り＋ずらし、極端な拡大の切り取り。"""
        g, r = self.g, self.r
        for _ in range(int(1 + g.disorder * 3)):
            im = self.canvas.convert("RGB")
            if r.random() < .5:  # 斜めに切って片側をずらす
                a = r.uniform(-.6, .6)
                x0 = r.randint(W // 5, W * 4 // 5)
                m = Image.new("L", (W, H), 0)
                ImageDraw.Draw(m).polygon([(x0, 0), (W, 0), (W, H), (x0 + a * H, H)], fill=255)
                dx, dy = r.randint(-70, 70), r.randint(-110, 110)
                shifted = ImageChops.offset(im, dx, dy)
                im = Image.composite(shifted, im, m)
                self.trace.append(dict(kind="cut", box=(x0, 0, W, H), angle=math.degrees(a), on_grid=False))
            else:  # 一部を拡大して上に貼る
                w, h = r.randint(120, 260), r.randint(120, 260)
                x, y = r.randint(0, W - w), r.randint(0, H - h)
                crop = im.crop((x, y, x + w, y + h)).resize((int(w * r.uniform(2, 3.2)), int(h * r.uniform(2, 3.2))), Image.NEAREST)
                im.paste(crop, (x - r.randint(0, 150), y - r.randint(0, 150)))
                self.trace.append(dict(kind="zoomcut", box=(x, y, x + crop.width, y + crop.height), angle=0, on_grid=False))
            self.canvas = im.convert("RGBA")

    def build(self) -> Image.Image:
        g = self.g
        rects = self.regions()
        for i, kind in self.kinds(rects).items():
            self.fill(rects[i], kind)
        self.swiss()
        self.scatter()
        self.headline()
        self.destroy_order()
        # 破壊のあとに雑誌の顔を載せる：読めなくなることを避ける
        self.masthead()
        self.furniture()
        grain = xerox_grain((W, H), seed=g.seed, strength=.5 + g.mix["punk"] * .8, toner=.8)
        self.canvas.alpha_composite(grain)
        return self.canvas.convert("RGB")


def render(g: Genome) -> tuple[Image.Image, list[dict]]:
    c = Cover(g)
    img = c.build()
    return img, c.trace


# ---------- 採点 ----------

def aesthetic(img: Image.Image, trace: list[dict], g: Genome) -> dict:
    """美的完成度。新規性とは別に採点する。各項目 0〜1、total は重み付き平均。

    density   情報密度：地（墨）のままの面積が少ない（0.75〜0.97 を満点とする）
    tension   秩序×無秩序：グリッドに載った部品の割合と、傾き・切断の割合の両方が大きい（小さいほうを採る）
    focal     主役が見える：最大の領域が画面の 12〜45%、かつ全体が一様でない（輝度の分散）
    contrast  明暗の幅：輝度ヒストグラムが両端まで使われている
    palette   色の統制：色相のうち強い色が少数に絞られている（毒々しいが散らからない）
    masthead  題字が見える：題字の領域のコントラストが十分
    """
    a = np.asarray(img.resize((300, 400)), dtype=np.float32) / 255
    lum = a @ np.array([.2126, .7152, .0722], dtype=np.float32)
    sumi = np.array(_rgb("sumi"), dtype=np.float32) / 255
    bare = float((np.abs(a - sumi).sum(axis=2) < .06).mean())
    density = float(np.clip(1 - abs((1 - bare) - .86) / .25, 0, 1))
    elems = [t for t in trace if t["kind"] not in ("cut", "zoomcut")]
    on_grid = np.mean([t["on_grid"] for t in elems]) if elems else 0
    tilted = np.mean([abs(t["angle"]) > 3 for t in elems]) + (.2 if any(t["kind"] in ("cut", "zoomcut") for t in trace) else 0)
    tension = float(np.clip(min(on_grid / .45, np.clip(tilted, 0, 1) / .3), 0, 1))
    hero = [t for t in trace if t["kind"] == "hero"]
    share = ((hero[0]["box"][2] - hero[0]["box"][0]) * (hero[0]["box"][3] - hero[0]["box"][1]) / (W * H)) if hero else 0
    focal = float(np.clip(1 - abs(share - .28) / .25, 0, 1) * np.clip(lum.std() / .25, 0, 1))
    p5, p95 = np.percentile(lum, [5, 95])
    contrast = float(np.clip((p95 - p5) / .8, 0, 1))
    hsv = np.array([colorsys.rgb_to_hsv(*px) for px in a.reshape(-1, 3)[::7]])
    strong = hsv[(hsv[:, 1] > .45) & (hsv[:, 2] > .35)]
    if len(strong) < 50:
        palette = .4
    else:
        hist, _ = np.histogram(strong[:, 0], bins=12, range=(0, 1))
        top = np.sort(hist)[::-1] / hist.sum()
        palette = float(np.clip(1 - abs(top[:4].sum() - .85) / .4, 0, 1))
    mh = [t for t in trace if t["kind"] == "masthead"]
    if mh:
        x0, y0, x1, y1 = (int(max(0, v) * s) for v, s in zip(mh[0]["box"], (.25, .25, .25, .25)))
        x1, y1 = min(x1, 300), min(y1, 400)
        reg = lum[y0:y1, x0:x1]
        masthead = float(np.clip(reg.std() / .2, 0, 1)) if reg.size > 20 else 0
    else:
        masthead = 0
    parts = dict(density=density, tension=tension, focal=focal, contrast=contrast, palette=palette, masthead=masthead)
    wts = dict(density=1, tension=1.4, focal=1.2, contrast=.8, palette=1, masthead=1.2)
    parts["total"] = float(sum(parts[k] * wts[k] for k in wts) / sum(wts.values()))
    return {k: round(v, 3) for k, v in parts.items()}


def features(img: Image.Image, g: Genome) -> dict:
    """新規性の計算に使う特徴：見た目（縮小画像・色相の分布）と、作り方（遺伝子）。"""
    small = np.asarray(ImageOps.grayscale(img).resize((12, 16), Image.BOX), dtype=np.float32) / 255
    a = np.asarray(img.resize((60, 80)), dtype=np.float32) / 255
    hsv = np.array([colorsys.rgb_to_hsv(*px) for px in a.reshape(-1, 3)])
    sel = hsv[(hsv[:, 1] > .35) & (hsv[:, 2] > .3)]
    hue = np.histogram(sel[:, 0], bins=12, range=(0, 1))[0].astype(np.float32) if len(sel) else np.zeros(12, np.float32)
    hue = hue / max(hue.sum(), 1)
    return dict(
        thumb=small.ravel().round(3).tolist(), hue=hue.round(3).tolist(),
        mix=[round(g.mix[k], 3) for k in REFS], cols=g.cols, masthead=g.masthead, hero=g.hero,
        accents=sorted(g.accents), layout=g.layout, splits=g.splits,
    )


def distance(f1: dict, f2: dict) -> float:
    """0（同じ）〜1 前後（かけ離れている）。見た目 0.5：作り方 0.5。"""
    thumb = float(np.abs(np.array(f1["thumb"]) - np.array(f2["thumb"])).mean() / .35)
    hue = float(np.abs(np.array(f1["hue"]) - np.array(f2["hue"])).sum() / 2)
    mix = float(np.abs(np.array(f1["mix"]) - np.array(f2["mix"])).sum() / 2)
    cat = np.mean([f1["masthead"] != f2["masthead"], f1["hero"] != f2["hero"], f1["layout"] != f2["layout"],
                   f1["cols"] != f2["cols"], set(f1["accents"]) != set(f2["accents"])])
    look = min(1.0, .6 * thumb + .4 * hue)
    how = min(1.0, .5 * mix + .5 * cat)
    return float(.5 * look + .5 * how)


def novelty(f: dict, history: list[dict]) -> float:
    """過去のどれとも似ていないほど 1 に近い。最も近い過去作との距離（履歴がなければ 1）。"""
    if not history:
        return 1.0
    return float(min(1.0, min(distance(f, h) for h in history) / .55))


# ---------- 生成の入口 ----------

def load_history(out_dir: Path) -> list[dict]:
    p = out_dir / "history.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def generate(n: int = 12, keep: int = 3, out_dir: Path | str = "out/collage", seed0: int | None = None,
             min_aesthetic: float = .55, log=print) -> list[dict]:
    """n 枚作る → 美的完成度が min_aesthetic 以上のものを候補に → 新規性の高い順に keep 枚を残す。

    同じ回の中でも、すでに選んだものと似ていれば新規性を下げて選び直す（貪欲法）。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    history = load_history(out)
    seed0 = seed0 if seed0 is not None else random.SystemRandom().randrange(10 ** 6)
    cands = []
    for i in range(n):
        g = sample_genome(seed0 + i)
        img, trace = render(g)
        ae = aesthetic(img, trace, g)
        f = features(img, g)
        cands.append(dict(g=g, img=img, aesthetic=ae, feat=f, seed=g.seed))
        log(f"  seed {g.seed}: aesthetic {ae['total']:.2f}  {g.masthead}/{g.hero}/{g.layout}")
    ok = [c for c in cands if c["aesthetic"]["total"] >= min_aesthetic] or sorted(cands, key=lambda c: -c["aesthetic"]["total"])[:keep]
    chosen: list[dict] = []
    pool = list(history)
    while ok and len(chosen) < keep:
        for c in ok:
            c["novelty"] = novelty(c["feat"], pool)
        best = max(ok, key=lambda c: (c["novelty"], c["aesthetic"]["total"]))
        ok.remove(best)
        chosen.append(best)
        pool.append(best["feat"])
    records = []
    for c in chosen:
        name = f"cover_{c['seed']}"
        c["img"].save(out / f"{name}.png")
        rec = dict(name=name, seed=c["seed"], aesthetic=c["aesthetic"], novelty=round(c["novelty"], 3),
                   genome=asdict(c["g"]))
        (out / f"{name}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        history.append(c["feat"])
        records.append(rec)
        log(f"→ {name}.png  aesthetic {c['aesthetic']['total']:.2f} / novelty {c['novelty']:.2f}")
    (out / "history.json").write_text(json.dumps(history), encoding="utf-8")
    return records
