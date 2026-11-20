"""YŌGEN のロゴと英字の題字。決まった処理と設定値をここに記録する。

  wordmark()  英字「yōgen」：Archivo Black の小文字を字が重なるほど詰め（字間 -0.14）、
              ピンボケ（degrade.defocus、ぼけ半径 0.035、右ほど強く字ごとにむら、薄い二重像、
              ほこりの粒なし）。基本は藤黄の地に黒。
  logo()      ロゴ：篆書の「妖幻」のみ（assets/seal/yougen.png）。英字と同じピンボケ処理
              （ぼけ半径だけ 0.022。線が細く、0.035 だと「幻」の形が埋まる）。

色は明治の赤絵のトークン（墨・藤黄・洋紅）。
"""
from __future__ import annotations

from PIL import Image

from .config import ROOT
from .degrade import defocus, tight_text

SUMI = (22, 19, 15)
TOO = (232, 179, 38)
YOKO = (200, 23, 79)
WHITE = (244, 242, 236)

FONT = ROOT / "assets" / "fonts" / "archivo" / "Archivo-Black.ttf"
SEAL = ROOT / "assets" / "seal" / "yougen.png"

# 記録した設定値
WORDMARK = dict(text="yōgen", size=400, track=-.14, seed=5, radius=.035)
LOGO = dict(seed=5, radius=.022)  # 篆書は線が細いので英字より弱め


def _colored(mask: Image.Image, color, width: int | None = None) -> Image.Image:
    if width:
        mask = mask.resize((width, int(mask.height * width / mask.width)), Image.LANCZOS)
    out = Image.new("RGBA", mask.size, (*color, 0))
    out.putalpha(mask)
    return out


def wordmark_mask() -> Image.Image:
    w = WORDMARK
    return defocus(tight_text(w["text"], FONT, w["size"], track=w["track"]), seed=w["seed"], radius=w["radius"])


def logo_mask() -> Image.Image:
    seal = Image.open(SEAL).convert("L")
    return defocus(seal, seed=LOGO["seed"], radius=LOGO["radius"])


def wordmark(color=SUMI, width: int | None = None) -> Image.Image:
    return _colored(wordmark_mask(), color, width)


def logo(color=WHITE, width: int | None = None) -> Image.Image:
    return _colored(logo_mask(), color, width)


def on_ground(layer: Image.Image, ground, size, scale: float = .85) -> Image.Image:
    """地の色の上に中央寄せで置く。"""
    W, H = size
    w = int(min(W * scale, H * scale * layer.width / layer.height))
    lay = layer.resize((w, int(layer.height * w / layer.width)), Image.LANCZOS)
    c = Image.new("RGBA", (W, H), (*ground, 255))
    c.alpha_composite(lay, ((W - lay.width) // 2, (H - lay.height) // 2))
    return c
