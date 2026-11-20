"""文字を「劣化」させる処理。参照：コピーを重ねた TRASH MACHINE、ピンボケの coture studio。

どちらも均一なフィルターではなく、場所ごとにばらつく。そのばらつきを作るのがこのモジュールの役目。

  photocopy(mask)  コピーのコピー：輪郭が大小2段階で不揃いに膨らみ欠け、角と内側が埋まり、
                   低解像度を拡大したギザギザ、ところどころの垂れ、トナーの粒と抜け
  defocus(mask)    ピンボケ：場所ごとにぼけの強さが違い（片側ほど強い＋字ごとの差）、
                   少しずれた二重像、真っ黒な芯、境目だけの粒子、ほこり
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _rng(seed):
    return np.random.default_rng(seed)


def _field(shape, cell: float, rng) -> np.ndarray:
    """0〜1 の滑らかな乱数の場。cell は模様の大きさ（px）。"""
    h, w = shape
    gh, gw = max(2, int(h / cell) + 3), max(2, int(w / cell) + 3)
    g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8))
    return np.asarray(g.resize((w, h), Image.BICUBIC)).astype(np.float32) / 255


def _pad(m: Image.Image, p: int) -> Image.Image:
    out = Image.new("L", (m.width + 2 * p, m.height + 2 * p), 0)
    out.paste(m, (p, p))
    return out


def tight_text(text: str, font_path, size: int = 400, track: float = -.14, line_gap: float = -.18,
               stretch: float = 1.0) -> Image.Image:
    """字間を重なるほど詰めて組む。改行で行も詰める。stretch で縦長にする（1.3 なら高さ 1.3 倍）。"""
    f = ImageFont.truetype(str(font_path), size)
    lines = text.split("\n")
    widths = [sum(f.getlength(c) for c in l) for l in lines]
    W = int(max(widths) + size)
    H = int(size * (1.3 + (1 + line_gap) * (len(lines) - 1)) + size * .4)
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for i, l in enumerate(lines):
        x = size * .2
        y = size * .15 + i * size * (1 + line_gap)
        for c in l:
            d.text((x, y), c, font=f, fill=255)
            x += f.getlength(c) + size * track
    m = m.crop(m.getbbox())
    if stretch != 1.0:
        m = m.resize((m.width, int(m.height * stretch)), Image.LANCZOS)
    return m


def photocopy(mask: Image.Image, seed: int = 1, strength: float = 1.0, lowres: int = 90) -> Image.Image:
    rng = _rng(seed)
    h0 = mask.height
    pad = int(h0 * .18)
    m = _pad(mask, pad)
    W, H = m.size
    # 1) 低い解像度でコピーした状態を作る（字の高さを lowres px 前後に落とす）
    k = lowres / h0
    small = m.resize((max(8, int(W * k)), max(8, int(H * k))), Image.BILINEAR)
    s = small.size
    # 2) 角と内側を埋める：太らせてから少し戻す
    small = small.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.9))
    a = np.asarray(small).astype(np.float32) / 255
    # 3) 輪郭のうねり（大）とこぶ（小）を場所ごとに変える
    big = _field(a.shape, 9, rng) - .5
    lump = _field(a.shape, 2.2, rng) - .5
    a = a + big * .32 * strength + lump * .26 * strength
    small = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))
    # 4) 拡大してしきい値：わずかなギザギザが残る
    up = small.resize((W, H), Image.BILINEAR)
    a = np.asarray(up).astype(np.float32) / 255
    a = a + (_field(a.shape, 40, rng) - .5) * .08
    ink = a > .5
    # 5) 垂れ：下端からところどころ
    img = Image.fromarray((ink * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    cols = np.nonzero(ink.any(axis=0))[0]
    r = np.random.default_rng(seed + 7)
    for _ in range(int(len(cols) / (h0 * .35) * strength)):
        x = int(r.choice(cols))
        ys = np.nonzero(ink[:, x])[0]
        y0 = int(ys.max())
        L = int(r.exponential(h0 * .07))
        wd = max(3, int(r.uniform(.02, .05) * h0))
        if L > h0 * .02:
            d.rounded_rectangle((x - wd // 2, y0 - wd, x + wd // 2, y0 + L), radius=wd // 2, fill=255)
    a = np.asarray(img).astype(np.float32) / 255
    # 6) トナーの抜け（固まって）と外の粒
    holes = (_field(a.shape, h0 * .03, r) > .86) & (r.random(a.shape) > .35)
    flecks = (r.random(a.shape) > .9992) & (np.asarray(m.filter(ImageFilter.GaussianBlur(h0 * .08))) > 10)
    a = np.where(holes, 0, a)
    a = np.maximum(a, flecks.astype(np.float32))
    out = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3) if h0 > 300 else ImageFilter.BLUR)
    return out.filter(ImageFilter.GaussianBlur(1.0)).point(lambda v: 255 if v > 120 else 0).filter(ImageFilter.GaussianBlur(.7))


def ink_bleed(mask: Image.Image, seed: int = 1, spread: float = .03, wobble: float = 1.0,
              drips: float = .35, specks: float = 0.0, lump: float = 1.0, lowres: int = 110) -> Image.Image:
    """インクのにじみ（TRASH MACHINE）：紙に染みて字が太り、輪郭が場所ごとに不揃いに膨らむ。

    spread は字の高さに対するにじみ幅。場所ごとにその 0.4〜1.6 倍でばらつく。
    """
    rng = _rng(seed)
    h0 = mask.height
    R = spread * h0
    pad = int(R * 5 + h0 * .12)
    m = _pad(mask, pad)
    H, W = m.size[1], m.size[0]
    # 1) 場所ごとに違う量だけ染みる：ぼかしの強さを場で混ぜる
    levels = [R * f for f in (.4, .8, 1.25, 1.7)]
    stack = np.stack([np.asarray(m.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255 for r in levels])
    field = _field((H, W), h0 * .22, rng)
    pos = field * (len(levels) - 1)
    i0 = np.clip(np.floor(pos).astype(int), 0, len(levels) - 2)
    t = pos - i0
    yy, xx = np.arange(H)[:, None], np.arange(W)[None, :]
    a = stack[i0, yy, xx] * (1 - t) + stack[i0 + 1, yy, xx] * t
    # 2) 紙の繊維に沿った不揃い：中くらいのこぶと細かいけば
    a = a + (_field((H, W), h0 * .06 * lump, rng) - .5) * .22 * wobble
    a = a + (_field((H, W), h0 * .02 * lump, rng) - .5) * .07 * wobble
    # 3) 少し低めのしきい値で太らせる（角が丸く、狭いところが少し埋まる）
    ink = a > .40
    # 4) 下端から短い垂れ（にじみが溜まって落ちた程度）
    img = Image.fromarray((ink * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    r = np.random.default_rng(seed + 11)
    cols = np.nonzero(ink.any(axis=0))[0]
    for _ in range(int(len(cols) / (h0 * .5) * drips)):
        x = int(r.choice(cols))
        y0 = int(np.nonzero(ink[:, x])[0].max())
        L = int(r.exponential(h0 * .045)) + int(h0 * .01)
        wd = max(4, int(r.uniform(.03, .07) * h0))
        d.ellipse((x - wd / 2, y0 - wd * .3, x + wd / 2, y0 + L), fill=255)
    # 5) 拡大コピーのわずかなギザギザと、トナーの抜け・外の粒
    k = lowres / h0
    sm = img.resize((max(8, int(W * k)), max(8, int(H * k))), Image.BILINEAR)
    img = sm.resize((W, H), Image.BILINEAR)
    a = np.asarray(img).astype(np.float32) / 255
    a = (a > .5).astype(np.float32)
    holes = (_field(a.shape, h0 * .02, r) > .965) & (r.random(a.shape) > .6)
    a = np.where(holes & (a > 0), 0, a)
    near = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(h0 * .06))) > 6
    flecks = (r.random(a.shape) > 1 - .0015 * specks) & near
    a = np.maximum(a, flecks)
    out = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    return out.filter(ImageFilter.GaussianBlur(.9)).point(lambda v: 255 if v > 120 else 0).filter(ImageFilter.GaussianBlur(.6))


def grainy(mask: Image.Image, seed: int = 4, edge: float = .012, salt: float = .1, patch: float = .35,
           grain_px: int = 2) -> Image.Image:
    """インクの粒子感：輪郭をディザで溶かし、中に抜けの点、濃さのむら。外へ飛ぶ粒は作らない。

    edge は輪郭のざらつく幅（字の高さに対する割合）。grain_px は粒の大きさ。
    """
    rng = _rng(seed)
    h0 = mask.height
    W, H = mask.size
    gw, gh = max(2, W // grain_px), max(2, H // grain_px)
    # 輪郭：少しぼかした値を、粒の大きさの乱数としきい値で比べる（ディザ）
    soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(max(1, edge * h0)))).astype(np.float32) / 255
    noise = np.asarray(Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8)).resize((W, H), Image.NEAREST)).astype(np.float32) / 255
    ink = soft > (noise * .9 + .05)
    # 中の抜け：濃さのむらが薄いところほど多く抜ける
    p = _field((H, W), h0 * .25, rng)
    noise2 = np.asarray(Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8)).resize((W, H), Image.NEAREST)).astype(np.float32) / 255
    holes = noise2 < salt * (1 + (1 - p) * patch * 3)
    a = (ink & ~holes).astype(np.float32)
    # 濃さのむら（白インクでも少し透ける）
    a = a * (1 - patch * .35 + p * patch * .35)
    return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))


def defocus(mask: Image.Image, seed: int = 2, radius: float = .05, skew: float = 1.0,
            ghost: tuple[float, float] = (.025, -.01), grain: float = .3, dust: bool = False) -> Image.Image:
    """radius・ghost は字の高さに対する割合。skew は右へ行くほどぼける度合い。"""
    rng = _rng(seed)
    h0 = mask.height
    R = radius * h0
    pad = int(R * 4 + h0 * .1)
    m = _pad(mask, pad)
    W, H = m.size
    # 二重像：少しずらした薄い写り
    gx, gy = int(ghost[0] * h0), int(ghost[1] * h0)
    g = Image.new("L", m.size, 0)
    g.paste(m, (gx, gy))
    base = np.maximum(np.asarray(m).astype(np.float32), np.asarray(g).astype(np.float32) * .55)
    base_img = Image.fromarray(base.astype(np.uint8))
    # ぼけの強さの場：右ほど強く＋字ごと・場所ごとのむら
    xs = np.linspace(0, 1, W)[None, :].repeat(H, 0)
    wfield = np.clip(.25 + xs * .75 * skew + (_field((H, W), h0 * .35, rng) - .5) * .7, 0, 1)
    levels = [R * f for f in (.35, .75, 1.3, 2.1)]
    blurred = [np.asarray(base_img.filter(ImageFilter.GaussianBlur(max(.5, r)))).astype(np.float32) / 255 for r in levels]
    pos = wfield * (len(levels) - 1)
    i0 = np.clip(np.floor(pos).astype(int), 0, len(levels) - 2)
    t = pos - i0
    stack = np.stack(blurred)
    a = stack[i0, np.arange(H)[:, None], np.arange(W)[None, :]] * (1 - t) + \
        stack[i0 + 1, np.arange(H)[:, None], np.arange(W)[None, :]] * t
    # 真っ黒な芯：トーンを立てる
    a = np.clip((a - .12) / .55, 0, 1) ** .85
    # 境目の粒子
    edge = a * (1 - a) * 4
    a = np.clip(a + rng.normal(0, grain, a.shape) * edge, 0, 1)
    if not dust:
        return Image.fromarray((a * 255).astype(np.uint8))
    # ほこり：芯の中の白い点、外の黒い点
    dust_in = (rng.random(a.shape) > .9985) & (a > .8)
    dust_out = (rng.random(a.shape) > .99965) & (a < .1)
    dust = Image.fromarray(((dust_in | dust_out) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    dmask = np.asarray(dust) > 0
    a = np.where(dmask & (a > .5), 0, np.where(dmask, 1, a))
    return Image.fromarray((a * 255).astype(np.uint8))
