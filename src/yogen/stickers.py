"""切り貼り用の素材（ステッカー）。materials/stickers.yaml のレシピから作る。

自作のアイコン（icons.py）の代わりに、本物のパブリックドメインの図版から切り出したものを貼る。
  sticker(key)              原画の色のまま（method: cutout / key / torn）
  sticker(key, ink=..., paper=...)  2色刷り（墨＋差し色）
"""
from __future__ import annotations

from functools import lru_cache

import yaml
from PIL import Image

from .materials import MAT_DIR, cutout, duotone, open_material, torn

RECIPES = MAT_DIR / "stickers.yaml"


def recipes() -> dict[str, list[dict]]:
    return yaml.safe_load(RECIPES.read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def _base(key: str, index: int) -> Image.Image:
    r = recipes()[key][index]
    im = open_material(r["material"])
    if r.get("crop"):
        l, t, rr, b = r["crop"]
        W, H = im.size
        im = im.crop((int(l * W), int(t * H), int(rr * W), int(b * H)))
    im.thumbnail((1400, 1400))
    if r["method"] == "cutout":
        return cutout(im)
    if r["method"] == "key":
        return _key(im, r.get("tol", 38))
    return torn(im, amp=max(8, min(im.size) // 45), seed=index + 3)


def _key(im: Image.Image, tol: float) -> Image.Image:
    """無地の地（絹や紙）の上に描かれたものを、地の色との差で抜く。"""
    import numpy as np
    from PIL import ImageFilter

    a = np.asarray(im.convert("RGB")).astype(np.float32)
    bg = np.median(a.reshape(-1, 3), axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(axis=2))
    m = Image.fromarray((np.clip((d - tol) / 25, 0, 1) * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    out = im.convert("RGBA")
    out.putalpha(m)
    return out.crop(m.point(lambda v: 255 if v > 40 else 0).getbbox())


def sticker(key: str, index: int = 0, ink=None, paper=None) -> Image.Image:
    """透明の地のステッカー（RGBA）。ink と paper を渡すと2色刷り。"""
    base = _base(key, index)
    if ink is None:
        return base.copy()
    out = duotone(base.convert("RGB"), ink, paper)
    out.putalpha(base.getchannel("A"))
    return out
