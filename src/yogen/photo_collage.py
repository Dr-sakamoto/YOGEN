"""写真だけのコラージュ。工芸品の写真の切り抜きだけで画面を埋める（下地を敷かない）。

方針：充足感を保つ。物の個数ではなく「埋まった割合」を目標にして、いちばん空いている場所に置いていく。
  1. 主役（HERO）の位置と形を先に決める。描くのは最後で、最前面に出る
  2. 残りは空いている場所に、広ければ中（MID）、狭ければ小（SMALL）を置く
  3. 埋まった割合が target を超えるか、max_obj 個に達したら止める

大きさの段は画面の幅に対する長辺の割合（幅 1200 なら 主役 780〜920 / 中 280〜430 / 小 150〜230 px）。
reserve に箱を渡すと、その場所は埋まったものとして扱う。後で題字や色面を載せる場所を先に取るため。

素材は materials/index.yaml のパブリックドメイン（CC0）の工芸品の写真だけ。
"""
from __future__ import annotations

import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .materials import cutout, open_material, place

HERO, MID, SMALL = (.65, .77), (.233, .358), (.125, .192)
OBJECTS = ['goldfish_inro', 'netsuke_cat', 'netsuke_cat_bowl', 'netsuke_daruma', 'netsuke_fox', 'netsuke_oni',
           'netsuke_oni_mask', 'netsuke_oni_red', 'netsuke_skeleton_drum', 'netsuke_skull', 'netsuke_skull_small']
HERO_OK = ['netsuke_oni_mask', 'netsuke_oni_red', 'netsuke_cat', 'netsuke_fox', 'netsuke_skull', 'netsuke_daruma']
HERO_SPOTS = [(.36, .33), (.66, .70)]  # 三分割の交点付近
SUMI = (22, 19, 15)
Q = 4  # 埋まり具合は 1/4 の解像度で数える


def clean(im: Image.Image) -> Image.Image:
    """切り抜きの縁に残る床・影の灰色（色味のない明るい画素）を落とす。"""
    a = np.asarray(im).astype(np.float32)
    rgb = a[..., :3]
    sat = (rgb.max(2) - rgb.min(2)) / np.maximum(rgb.max(2), 1)
    al = im.getchannel("A")
    er = al.resize((max(1, al.width // 4), max(1, al.height // 4))).filter(ImageFilter.MinFilter(31)).resize(al.size)
    band = np.asarray(al).astype(np.float32) - np.asarray(er).astype(np.float32)
    m = np.asarray(al).astype(np.float32).copy()
    m[(sat < .13) & (rgb.max(2) > 95) & (band > 40)] = 0
    al2 = Image.fromarray(m.astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(.8))
    out = im.copy()
    out.putalpha(al2)
    return out.crop(al2.getbbox() or (0, 0) + im.size)


@lru_cache(maxsize=32)
def _cut(key: str) -> Image.Image:
    im = open_material(key)
    im.thumbnail((1400, 1400))  # 主役でも長辺 920px 程度なので、元の解像度は要らない
    return clean(cutout(im, shrink=4))


class _Filler:
    def __init__(self, W: int, H: int, r: random.Random):
        self.W, self.H, self.r = W, H, r
        self.cov = np.zeros((H // Q, W // Q), bool)

    def make(self, key: str, side: float) -> Image.Image:
        im = _cut(key)
        if self.r.random() < .4:
            im = ImageOps.mirror(im)
        s = side / max(im.size)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        return im.rotate(self.r.uniform(-30, 30), resample=Image.BICUBIC, expand=True)

    def mark(self, im: Image.Image, xy):
        """置いた物の形を埋まり具合に足す。"""
        a = im.getchannel("A").resize((max(1, im.width // Q), max(1, im.height // Q)))
        m = np.asarray(a) > 128
        x, y = int(xy[0] // Q), int(xy[1] // Q)
        h, w = self.cov.shape
        x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x + m.shape[1]), min(h, y + m.shape[0])
        if x1 > x0 and y1 > y0:
            self.cov[y0:y1, x0:x1] |= m[y0 - y:y1 - y, x0 - x:x1 - x]

    def emptiest(self, radius: float):
        """空いている画素の密度を半径 radius でならし、いちばん空いている点と、その空き具合を返す。"""
        free = Image.fromarray((~self.cov * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(max(1, int(radius // Q))))
        f = np.asarray(free).astype(np.float32) / 255
        f = f + np.random.default_rng(self.r.randint(0, 9999)).random(f.shape) * .02  # 同点のときの偏りを崩す
        y, x = np.unravel_index(np.argmax(f), f.shape)
        return x * Q, y * Q, float(f[y, x])


def generate(seed: int, size=(1200, 1600), n_hero: int = 2, target: float = .985, max_obj: int = 220,
             reserve: list[tuple[int, int, int, int]] | None = None) -> tuple[Image.Image, dict]:
    """写真だけのコラージュ（RGB）と、埋まり具合の記録を返す。"""
    W, H = size
    r = random.Random(seed)
    f = _Filler(W, H, r)
    for x0, y0, x1, y1 in reserve or []:
        f.cov[y0 // Q:y1 // Q, x0 // Q:x1 // Q] = True

    heroes = []
    for cx, cy in HERO_SPOTS[:n_hero]:
        im = f.make(r.choice(HERO_OK), r.uniform(*HERO) * W)
        xy = (cx * W + r.uniform(-.05, .05) * W - im.width / 2, cy * H + r.uniform(-.04, .04) * H - im.height / 2)
        heroes.append((im, xy))
        f.mark(im, xy)

    placed = []
    while f.cov.mean() < target and len(placed) < max_obj:
        x, y, free = f.emptiest(MID[0] * W / 2)
        side = r.uniform(*(MID if free > .7 else SMALL)) * W
        im = f.make(r.choice(OBJECTS), side)
        xy = (x - im.width / 2 + r.uniform(-20, 20), y - im.height / 2 + r.uniform(-20, 20))
        placed.append((im, xy))
        f.mark(im, xy)

    c = Image.new("RGBA", (W, H), (*SUMI, 255))
    for im, xy in placed + heroes:
        place(c, im, xy, shadow=.6)
    out = c.convert("RGB")
    a = np.asarray(out).astype(int)
    bare = float((np.abs(a - np.array(SUMI)).sum(2) < 20).mean())
    return out, dict(seed=seed, objects=len(placed), heroes=n_hero, covered=float(f.cov.mean()), bare=bare)
