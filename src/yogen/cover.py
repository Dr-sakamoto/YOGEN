"""サムネイルのコラージュ。層として YAML に記録し、1枚の画像に合成する。

画面（board）は2つ。人がまず横のコンセプトアートを仕上げ、縦のショート表紙はそれを元に組み直す。
  concept  横 1920×1080。動画のサムネイル（書き出しは 1280×720 の JPEG も）。episodes/<id>/concept.yaml
  cover    縦 1080×1920（channel.yaml の render）。ショートの表紙。episodes/<id>/cover.yaml

エディタ（yogen studio）で組んだものと、ここでの書き出しは同じ数値から作る。

  座標    x, y は層の中心、w は幅（キャンバスの px）。
          rot は時計回りの角度、flip は左右反転。layers は下から上の順。
  地      墨で固定（ブランドの決まり）。
  層      fill      色面。色はその回の差し色（episode.yaml の colors）だけ
          artwork   主役の作品。原画の色のまま。crop は [左, 上, 右, 下] の割合
          sticker   切り抜き素材。色は付けず網点にする。点の色は下の地で決まる：
                    墨の地なら胡粉の点、色面の上なら墨の点（中心が載っている面で判定）
          logo      篆書の「妖幻」。色は下の地で決まる（墨の地なら胡粉、色面の上なら墨）
          wordmark  英字の題字「yōgen」。藤黄の地に黒（地の札ごと置く）
          text      英語の題。色は墨・胡粉・その回の差し色から選ぶ
"""
from __future__ import annotations

import math
import textwrap
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from .config import ROOT, channel_config
from .palette import ACCENTS, PALETTE, for_episode

FONTS_DIR = ROOT / "assets" / "fonts"
CACHE_DIR = ROOT / ".cache" / "parts"

HALFTONE_WIDTH = 900  # 網点のステッカーはこの幅で作ってから拡大縮小する（エディタと書き出しで同じ点になる）
HALFTONE_CELL = 9
WORDMARK_PAD = (.12, .22)  # 題字の札の余白（幅に対する割合：左右, 上下）


class _Layer(BaseModel):
    x: float
    y: float
    w: float = Field(gt=0)
    rot: float = 0
    flip: bool = False


class FillLayer(_Layer):
    kind: Literal["fill"] = "fill"
    h: float = Field(gt=0)
    color: str


class ArtworkLayer(_Layer):
    kind: Literal["artwork"] = "artwork"
    artwork: str = "main"
    crop: list[float] | None = Field(default=None, description="[左, 上, 右, 下] の割合")


class StickerLayer(_Layer):
    kind: Literal["sticker"] = "sticker"
    sticker: str
    index: int = 0


class LogoLayer(_Layer):
    kind: Literal["logo"] = "logo"


class WordmarkLayer(_Layer):
    kind: Literal["wordmark"] = "wordmark"


class TextLayer(_Layer):
    kind: Literal["text"] = "text"
    text: str
    font: str = "archivo/Archivo-ExpandedBlack.ttf"
    size: float = Field(default=120, gt=0)
    color: str = "gofun"
    w: float = 0  # 文字の層は size で大きさが決まる。w は使わない


Layer = Annotated[
    Union[FillLayer, ArtworkLayer, StickerLayer, LogoLayer, WordmarkLayer, TextLayer],
    Field(discriminator="kind"),
]


class Cover(BaseModel):
    layers: list[Layer] = Field(default_factory=list)


# ---------- 読み書きと検査 ----------

BOARDS = ("concept", "cover")
CONCEPT_SIZE = (1920, 1080)
THUMBNAIL_SIZE = (1280, 720)  # YouTube のサムネイルの推奨サイズ


def canvas_size(board: str = "cover") -> tuple[int, int]:
    if board == "concept":
        return CONCEPT_SIZE
    r = channel_config()["render"]
    return r["width"], r["height"]


def cover_path(ep_dir: Path, board: str = "cover") -> Path:
    if board not in BOARDS:
        raise ValueError(f"board は {BOARDS} のどれか: {board}")
    return ep_dir / f"{board}.yaml"


def load_cover(ep_dir: Path, board: str = "cover") -> Cover | None:
    p = cover_path(ep_dir, board)
    if not p.exists():
        return None
    return Cover.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def save_cover(ep_dir: Path, cover: Cover, board: str = "cover") -> Path:
    from .episode import _dump

    layers = []
    for layer in cover.layers:
        raw = {"kind": layer.kind}  # 種類を先頭に、既定値は省いて書く
        for k, v in layer.model_dump(mode="json", exclude_defaults=True).items():
            raw[k] = round(v, 1) if isinstance(v, float) else v
        layers.append(raw)
    p = cover_path(ep_dir, board)
    _dump({"layers": layers}, p)
    return p


def fonts() -> list[str]:
    return sorted(p.relative_to(FONTS_DIR).as_posix() for p in FONTS_DIR.glob("*/*.ttf"))


def check_cover(cover: Cover, ep) -> list[str]:
    """ブランドの決まりに合わない層を挙げる。空なら問題なし。"""
    from .stickers import recipes

    accents = [c.key for c in for_episode(ep)[1:]]
    arts = {a.key for a in ep.artworks}
    stick = recipes()
    errs = []
    for i, l in enumerate(cover.layers):
        at = f"層{i + 1}（{l.kind}）"
        if isinstance(l, FillLayer) and l.color not in accents:
            errs.append(f"{at}: 色面の色はその回の差し色 {accents} から（{l.color}）")
        if isinstance(l, TextLayer):
            if l.color not in ["sumi", "gofun", *accents]:
                errs.append(f"{at}: 文字の色は墨・胡粉・差し色 {accents} から（{l.color}）")
            if l.font not in fonts():
                errs.append(f"{at}: フォントがありません（{l.font}）")
        if isinstance(l, ArtworkLayer) and l.artwork not in arts:
            errs.append(f"{at}: episode.yaml に無い作品です（{l.artwork}）")
        if isinstance(l, StickerLayer) and not (l.sticker in stick and 0 <= l.index < len(stick[l.sticker])):
            errs.append(f"{at}: stickers.yaml に無い素材です（{l.sticker} #{l.index}）")
    return errs


# ---------- 地の判定 ----------

def _inside(px: float, py: float, f: FillLayer) -> bool:
    a = math.radians(-f.rot)
    dx, dy = px - f.x, py - f.y
    lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return abs(lx) <= f.w / 2 and abs(ly) <= f.h / 2


def ground_under(cover: Cover, i: int) -> str:
    """層 i の中心の下にある地の色（palette のキー）。色面が無ければ墨。"""
    l = cover.layers[i]
    for below in reversed(cover.layers[:i]):
        if isinstance(below, FillLayer) and _inside(l.x, l.y, below):
            return below.color
    return "sumi"


def dot_ink(ground: str) -> str:
    """墨の地では胡粉の点、色の地では墨の点。"""
    return "gofun" if ground == "sumi" else "sumi"


# ---------- 部品の画像（エディタと書き出しで共通） ----------

@lru_cache(maxsize=64)
def sticker_part(key: str, index: int, ink: str) -> Image.Image:
    """網点にしたステッカー（幅 HALFTONE_WIDTH）。重いのでディスクにも残す。"""
    from .stickers import halftone_sticker

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"sticker_{key}_{index}_{ink}_{HALFTONE_WIDTH}_{HALFTONE_CELL}.png"
    if p.exists():
        return Image.open(p).convert("RGBA")
    im = halftone_sticker(key, index, ink=PALETTE[ink].rgb, cell=HALFTONE_CELL, width=HALFTONE_WIDTH,
                          invert=ink == "gofun")
    im.save(p)
    return im


@lru_cache(maxsize=4)
def logo_part(color: str) -> Image.Image:
    from .brand import logo

    return logo(PALETTE[color].rgb, width=900)


@lru_cache(maxsize=1)
def wordmark_part() -> Image.Image:
    """藤黄の札に黒の「yōgen」。"""
    from .brand import wordmark

    wm = wordmark(PALETTE["sumi"].rgb, width=900)
    px, py = int(wm.width * WORDMARK_PAD[0]), int(wm.width * WORDMARK_PAD[1] / 2)
    plate = Image.new("RGBA", (wm.width + 2 * px, wm.height + 2 * py), (*PALETTE["too"].rgb, 255))
    plate.alpha_composite(wm, (px, py))
    return plate


def artwork_part(ep_dir: Path, key: str, crop: list[float] | None = None) -> Image.Image | None:
    from .sources import asset_path

    p = asset_path(ep_dir, key)
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    if crop:
        l, t, r, b = crop
        im = im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height)))
    return im


def text_part(l: TextLayer) -> Image.Image:
    font = ImageFont.truetype(str(FONTS_DIR / l.font), int(l.size))
    lines = l.text.split("\n") or [""]
    lh = int(l.size * 1.0)
    widths = [font.getlength(s) for s in lines]
    W, H = int(max(widths + [1])) + 2, lh * len(lines) + int(l.size * .3)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for n, (s, w) in enumerate(zip(lines, widths)):
        d.text(((W - w) / 2, n * lh), s, font=font, fill=(*PALETTE[l.color].rgb, 255))
    return im


# ---------- 合成 ----------

def _place(canvas: Image.Image, part: Image.Image, l, w: float | None = None, h: float | None = None):
    w = w or l.w
    h = h or part.height * w / part.width
    im = part.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
    if l.flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if l.rot:
        im = im.rotate(-l.rot, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(im, (round(l.x - im.width / 2), round(l.y - im.height / 2)))


def render_cover(cover: Cover, ep_dir: Path, size: tuple[int, int] | None = None,
                 board: str = "cover") -> Image.Image:
    """size を渡すとその大きさで描く（層の座標は board のキャンバスのまま、全体を縮める）。"""
    W, H = canvas_size(board)
    if size and size != (W, H):
        return render_cover(cover, ep_dir, board=board).resize(size, Image.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (*PALETTE["sumi"].rgb, 255))
    for i, l in enumerate(cover.layers):
        if isinstance(l, FillLayer):
            _place(canvas, Image.new("RGBA", (8, 8), (*PALETTE[l.color].rgb, 255)), l, l.w, l.h)
        elif isinstance(l, ArtworkLayer):
            part = artwork_part(ep_dir, l.artwork, l.crop)
            if part is None:
                raise FileNotFoundError(f"作品画像がありません。先に `yogen fetch {ep_dir.name}`")
            _place(canvas, part, l)
        elif isinstance(l, StickerLayer):
            _place(canvas, sticker_part(l.sticker, l.index, dot_ink(ground_under(cover, i))), l)
        elif isinstance(l, LogoLayer):
            _place(canvas, logo_part(dot_ink(ground_under(cover, i))), l)
        elif isinstance(l, WordmarkLayer):
            _place(canvas, wordmark_part(), l)
        elif isinstance(l, TextLayer):
            part = text_part(l)
            _place(canvas, part, l, part.width, part.height)
    return canvas.convert("RGB")


def default_cover(ep, board: str = "cover") -> Cover:
    """最初の雛形：差し色の帯、作品、題字。エディタで動かして使う。"""
    if board == "concept":
        return _rounded(default_concept(ep))
    return _rounded(_default_portrait(ep))


def _rounded(cover: Cover) -> Cover:
    """保存と同じ桁（小数1桁）にそろえる。"""
    data = cover.model_dump(mode="json")
    for raw in data["layers"]:
        for k, v in raw.items():
            if isinstance(v, float):
                raw[k] = round(v, 1)
    return Cover.model_validate(data)


def _default_portrait(ep) -> Cover:
    W, H = canvas_size()
    accent = [c.key for c in for_episode(ep)[1:]][0]
    art = ep.artworks[0]
    ratio = (art.height / art.width) if art.width and art.height else 1.45
    aw = min(W * .74, H * .6 / ratio)
    return Cover(layers=[
        FillLayer(x=W / 2, y=H * .6, w=W * 1.3, h=H * .22, rot=-6, color=accent),
        ArtworkLayer(x=W / 2, y=H * .14 + aw * ratio / 2, w=aw, artwork=art.key),
        WordmarkLayer(x=W / 2, y=H * .075, w=W * .38),
        TextLayer(x=W / 2, y=H * .86, text="\n".join(textwrap.wrap(ep.working_title.upper(), 20)[:3]),
                  size=60, color="gofun"),
    ])


def default_concept(ep) -> Cover:
    """横の雛形：右に作品、左に題字と題、斜めの差し色の帯。"""
    W, H = CONCEPT_SIZE
    accent = [c.key for c in for_episode(ep)[1:]][0]
    art = ep.artworks[0]
    ratio = (art.height / art.width) if art.width and art.height else 1.45
    aw = min(W * .46, H * .88 / ratio)
    return Cover(layers=[
        FillLayer(x=W * .36, y=H * .6, w=W * 1.0, h=H * .3, rot=-8, color=accent),
        ArtworkLayer(x=W * .72, y=H / 2, w=aw, rot=3, artwork=art.key),
        WordmarkLayer(x=W * .17, y=H * .14, w=W * .22),
        TextLayer(x=W * .26, y=H * .6, text="\n".join(textwrap.wrap(ep.working_title.upper(), 20)[:3]),
                  size=62, color="gofun"),
    ])
