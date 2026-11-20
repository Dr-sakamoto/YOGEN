"""美術館のオープンアクセスAPIから作品画像とメタデータを取得する。

パブリックドメインと確認できない作品は取得を止める（企画書「素材と情報源」）。
"""
from __future__ import annotations

from pathlib import Path

import requests
from PIL import Image

from .models import Artwork

UA = {"User-Agent": "yogen-factory/0.1", "AIC-User-Agent": "yogen-factory/0.1"}
TIMEOUT = 60


class NotPublicDomain(Exception):
    pass


def fetch_met(art: Artwork) -> Artwork:
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{art.object_id}"
    d = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    if not d.get("isPublicDomain"):
        raise NotPublicDomain(f"Met {art.object_id} はパブリックドメインではありません")
    return art.model_copy(update={
        "title": d.get("title"),
        "artist": d.get("artistDisplayName"),
        "date": d.get("objectDate"),
        "image_url": d.get("primaryImage"),
        "page_url": d.get("objectURL"),
        "credit": f"The Metropolitan Museum of Art, {d.get('creditLine', '')}".strip(", "),
        "license": "CC0 (Met Open Access)",
        "is_public_domain": True,
    })


def fetch_aic(art: Artwork) -> Artwork:
    fields = "id,title,artist_display,date_display,image_id,is_public_domain,credit_line"
    url = f"https://api.artic.edu/api/v1/artworks/{art.object_id}?fields={fields}"
    r = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    d, iiif = r["data"], r["config"]["iiif_url"]
    if not d.get("is_public_domain"):
        raise NotPublicDomain(f"AIC {art.object_id} はパブリックドメインではありません")
    # 所蔵館が持つ元の解像度で取る（ズームしても粗くならないように）
    info = requests.get(f"{iiif}/{d['image_id']}/info.json", headers=UA, timeout=TIMEOUT).json()
    return art.model_copy(update={
        "title": d.get("title"),
        "artist": " ".join((d.get("artist_display") or "").split("\n")[:1]),
        "date": d.get("date_display"),
        "image_url": f"{iiif}/{d['image_id']}/full/{info['width']},/0/default.jpg",
        "page_url": f"https://www.artic.edu/artworks/{d['id']}",
        "credit": f"Art Institute of Chicago, {d.get('credit_line', '')}".strip(", "),
        "license": "CC0 (Art Institute of Chicago)",
        "is_public_domain": True,
    })


def fetch_artwork(art: Artwork, assets_dir: Path) -> Artwork:
    """メタデータを埋め、画像を assets/<key>.jpg に保存して返す。"""
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / f"{art.key}.jpg"

    if art.source == "local":
        if not (art.license and art.is_public_domain):
            raise NotPublicDomain(
                f"local素材 {art.key}: license と is_public_domain: true を episode.yaml に手で記録してください"
            )
        Image.open(art.local_path).convert("RGB").save(dest, quality=95)
    else:
        art = fetch_met(art) if art.source == "met" else fetch_aic(art)
        if not art.image_url:
            raise RuntimeError(f"{art.source} {art.object_id}: 画像URLがありません")
        resp = requests.get(art.image_url, headers=UA, timeout=TIMEOUT)
        resp.raise_for_status()
        dest.write_bytes(resp.content)

    with Image.open(dest) as im:
        w, h = im.size
    return art.model_copy(update={"width": w, "height": h})


def asset_path(ep_dir: Path, key: str) -> Path:
    return ep_dir / "assets" / f"{key}.jpg"
