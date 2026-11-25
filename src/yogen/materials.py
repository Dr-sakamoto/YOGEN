"""切り貼りの素材（ファウンドイメージ）。

主役の作品とは別に、画面に貼る本物の図版を美術館のオープンアクセスから集める。
パブリックドメインと確認できたものだけを使い、出典は materials/index.yaml に記録する
（画像は git に入れず、必要なときに取り直す）。

  種類   object   立体物の写真（根付など）→ 背景を切り抜いて貼る
         ink      墨一色の版画・版本（北斎漫画・墨摺絵）→ コピー機にかけたような白黒
         print    色のある版画 → 紙片として、またはリソの2色刷りに
         textile  織物 → 地の質感
"""
from __future__ import annotations

import io
import random
from pathlib import Path

import numpy as np
import requests
import yaml
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from .config import ROOT

MAT_DIR = ROOT / "materials"
INDEX = MAT_DIR / "index.yaml"
UA = {"User-Agent": "yogen-factory/0.1", "AIC-User-Agent": "yogen-factory/0.1"}


# ---------- 取得と記録 ----------

def _met(obj_id: str) -> tuple[dict, str]:
    d = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}", headers=UA, timeout=60).json()
    if not d.get("isPublicDomain"):
        raise ValueError(f"Met {obj_id} はパブリックドメインではありません")
    rec = {"title": d.get("title"), "artist": d.get("artistDisplayName") or None, "date": d.get("objectDate"),
           "credit": "The Metropolitan Museum of Art", "license": "CC0 (Met Open Access)", "page_url": d.get("objectURL")}
    return rec, d.get("primaryImage") or d.get("primaryImageSmall")


def _aic(obj_id: str) -> tuple[dict, str]:
    r = requests.get(f"https://api.artic.edu/api/v1/artworks/{obj_id}",
                     params={"fields": "id,title,artist_title,date_display,image_id,is_public_domain"}, headers=UA, timeout=60).json()
    d, iiif = r["data"], r["config"]["iiif_url"]
    if not d.get("is_public_domain"):
        raise ValueError(f"AIC {obj_id} はパブリックドメインではありません")
    info = requests.get(f"{iiif}/{d['image_id']}/info.json", headers=UA, timeout=60).json()
    # 画像ごとに許可されたサイズがある。一覧の中で 2000px 以下の最大を使う
    sizes = [s["width"] for s in info.get("sizes", []) if s["width"] <= 2000] or [843]
    w = max(sizes)
    rec = {"title": d.get("title"), "artist": d.get("artist_title"), "date": d.get("date_display"),
           "credit": "Art Institute of Chicago", "license": "CC0 (Art Institute of Chicago)",
           "page_url": f"https://www.artic.edu/artworks/{d['id']}"}
    return rec, f"{iiif}/{d['image_id']}/full/{w},/0/default.jpg"


def load_index() -> dict:
    if INDEX.exists():
        return yaml.safe_load(INDEX.read_text(encoding="utf-8")) or {}
    return {}


def fetch(key: str, source: str, obj_id: str, kind: str, tags: list[str] | None = None) -> Path:
    """素材を取得して materials/<key>.jpg に置き、出典を index.yaml に記録する。"""
    MAT_DIR.mkdir(exist_ok=True)
    rec, url = (_met if source == "met" else _aic)(str(obj_id))
    path = MAT_DIR / f"{key}.jpg"
    if not path.exists():
        urls = [url]
        if "/full/" in url and source == "aic":
            # 大きいサイズが拒否される画像がある。順に小さくして取り直す
            base, rest = url.split("/full/")
            urls += [f"{base}/full/{w},/0/default.jpg" for w in (1686, 1200, 843)]
        for u in urls:
            resp = requests.get(u, headers=UA, timeout=120)
            if resp.ok:
                break
        resp.raise_for_status()
        Image.open(io.BytesIO(resp.content)).convert("RGB").save(path, quality=92)
    idx = load_index()
    idx[key] = {"source": source, "id": str(obj_id), "kind": kind, "tags": tags or [], **rec}
    INDEX.write_text(yaml.safe_dump(idx, allow_unicode=True, sort_keys=True, width=100), encoding="utf-8")
    return path


def open_material(key: str) -> Image.Image:
    path = MAT_DIR / f"{key}.jpg"
    if not path.exists():
        rec = load_index()[key]
        fetch(key, rec["source"], rec["id"], rec["kind"], rec.get("tags"))
    return Image.open(path).convert("RGB")


# ---------- 加工 ----------

def cutout(img: Image.Image, tol: float = 26, shrink: int = 2) -> Image.Image:
    """無地の背景で撮った立体物（根付など）を切り抜く。縁の色を背景とみなし、外側から塗りつぶして判定する。"""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w, _ = a.shape
    # 撮影の背景は上から下へのグラデーションが多いので、行ごとに左右の端の色を背景とみなす
    edge = max(4, w // 20)
    row_bg = np.median(np.concatenate([a[:, :edge], a[:, -edge:]], axis=1), axis=1)  # (h, 3)
    dist = np.sqrt(((a - row_bg[:, None, :]) ** 2).sum(axis=2))
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1)
    # 色味のない灰色（床・影）も背景とみなす。象牙などの物は少し色味がある
    like = (dist < tol) | ((sat < .09) & (dist < 90))
    like_bg = Image.fromarray((like * 255).astype(np.uint8))
    # 外側から背景らしい画素をたどる（中の白い部分は残す）
    flood = like_bg.copy()
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)):
        if flood.getpixel(seed) == 255:
            ImageDraw.floodfill(flood, seed, 128)
    outside = np.asarray(flood) == 128
    mask = Image.fromarray(((~outside) * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MinFilter(shrink * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out.crop(mask.getbbox() or (0, 0, w, h))


def _keep_big(mask: Image.Image, keep: float) -> Image.Image:
    """最大の塊の keep 倍より小さい島（飛び散った墨・紙の傷）を消す。"""
    k = 4
    small = mask.resize((mask.width // k, mask.height // k), Image.NEAREST).point(lambda v: 255 if v > 127 else 0)
    lab = small.copy()
    sizes = []
    for y in range(small.height):
        for x in range(small.width):
            if lab.getpixel((x, y)) == 255:
                c = 1 + len(sizes)
                ImageDraw.floodfill(lab, (x, y), c if c < 255 else 254)
                sizes.append(0)
    if not sizes:
        return mask
    arr = np.asarray(lab)
    counts = {i + 1: int((arr == min(i + 1, 254)).sum()) for i in range(len(sizes))}
    top = max(counts.values())
    good = np.zeros(arr.shape, bool)
    for c, n in counts.items():
        if n >= top * keep:
            good |= arr == min(c, 254)
    gm = Image.fromarray((good * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).resize(mask.size, Image.BILINEAR)
    from PIL import ImageChops
    return ImageChops.multiply(mask, gm.point(lambda v: 255 if v > 60 else 0))


def flood_cut(img: Image.Image, bg=None, tol: float = 40, shrink: int = 1, feather: float = 1.2, keep: float = .15) -> Image.Image:
    """版画の人物を切り抜く。外縁から地（紙・摺りの色）に近い画素をたどって抜き、残りを人物とする。

    bg: 地の色 [[r,g,b(,許容差)], ...]。省略すると画像の外縁の中央値。地が複数の色なら複数渡す。
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    if bg is None:
        ring = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
        bg = [np.median(ring, axis=0)]
    # 各色は [r, g, b] か [r, g, b, 許容差]。許容差を省略すると tol
    near = np.zeros((h, w), bool)
    for c in bg:
        t = c[3] if len(c) > 3 else tol
        near |= np.sqrt(((a - np.array(c[:3], dtype=np.float32)) ** 2).sum(axis=2)) < t
    like = Image.fromarray((near * 255).astype(np.uint8))
    flood = like.copy()
    for x in range(0, w, 6):
        for y in (0, h - 1):
            if flood.getpixel((x, y)) == 255:
                ImageDraw.floodfill(flood, (x, y), 128)
    for y in range(0, h, 6):
        for x in (0, w - 1):
            if flood.getpixel((x, y)) == 255:
                ImageDraw.floodfill(flood, (x, y), 128)
    outside = np.asarray(flood) == 128
    mask = Image.fromarray(((~outside) * 255).astype(np.uint8))
    mask = _keep_big(mask.filter(ImageFilter.MedianFilter(5)), keep)
    if shrink:
        mask = mask.filter(ImageFilter.MinFilter(shrink * 2 + 1))
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out.crop(mask.point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, w, h))


def xerox(img: Image.Image, ink=(22, 19, 15), paper=None, thresh: float = .55, grit: float = .08, seed: int = 1) -> Image.Image:
    """コピー機にかけたような白黒。暗いところをインク、明るいところを紙（paper=None なら透明）にする。"""
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    arr = np.asarray(g).astype(np.float32) / 255
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, grit, arr.shape)
    # トナーのむら：低い周波数の明暗
    low = np.asarray(Image.fromarray((rng.random((arr.shape[0] // 40 + 2, arr.shape[1] // 40 + 2)) * 255).astype(np.uint8))
                     .resize(arr.shape[::-1], Image.BICUBIC)).astype(np.float32) / 255
    ink_mask = (arr + noise + (low - .5) * .12) < thresh
    alpha = Image.fromarray((ink_mask * 255).astype(np.uint8))
    out = Image.new("RGBA", g.size, (*paper, 255) if paper else (0, 0, 0, 0))
    out.paste(Image.new("RGBA", g.size, (*ink, 255)), (0, 0), alpha)
    return out


def duotone(img: Image.Image, ink, paper) -> Image.Image:
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    return ImageOps.colorize(g, black=ink, white=paper).convert("RGBA")


def torn(img: Image.Image, amp: int = 10, seed: int = 3, paper=None, paper_w: int = 0) -> Image.Image:
    """ちぎった縁。paper を指定すると、縁に紙の白い耳を残す。"""
    r = random.Random(seed)
    w, h = img.size
    pts = []
    step = max(8, min(w, h) // 30)
    for x in range(0, w + step, step):
        pts.append((min(x, w), r.uniform(0, amp)))
    for y in range(0, h + step, step):
        pts.append((w - r.uniform(0, amp), min(y, h)))
    for x in range(w, -step, -step):
        pts.append((max(x, 0), h - r.uniform(0, amp)))
    for y in range(h, -step, -step):
        pts.append((r.uniform(0, amp), max(y, 0)))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    base = img.convert("RGBA")
    if paper:
        inner = m.filter(ImageFilter.MinFilter(paper_w * 2 + 1))
        bg = Image.new("RGBA", (w, h), (*paper, 255))
        bg.paste(base, (0, 0), inner)
        base = bg
    a = ImageChops.multiply(base.getchannel("A"), m)
    base.putalpha(a)
    return base


def place(canvas: Image.Image, layer: Image.Image, xy, scale: float = 1.0, angle: float = 0, shadow: float = .45):
    """紙片を貼る：拡大縮小・回転・落ち影。"""
    if scale != 1:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.LANCZOS)
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    if shadow:
        sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sh.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * shadow)))
        canvas.alpha_composite(sh, (int(xy[0] + 8), int(xy[1] + 12)))
    canvas.alpha_composite(layer, (int(xy[0]), int(xy[1])))
    return canvas
