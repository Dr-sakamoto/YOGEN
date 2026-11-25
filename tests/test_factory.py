import shutil
from pathlib import Path

import pytest
import yaml
from PIL import Image

from yogen import cli
from yogen.models import Episode, Script, Status
from yogen.render import build_ass, render_episode
from yogen.tts import speakable
from yogen.upload import build_body

FIXTURES = Path(__file__).parent / "fixtures"


def sample_script() -> Script:
    return Script.model_validate(yaml.safe_load((FIXTURES / "sample_script.yaml").read_text()))


def sample_episode(tmp_path: Path, **kw) -> Episode:
    assets = tmp_path / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (600, 900), (180, 160, 120)).save(assets / "main.jpg")
    data = dict(
        id="t", working_title="t", research_notes="n",
        artworks=[{"key": "main", "source": "local", "local_path": "x", "width": 600, "height": 900}],
    )
    data.update(kw)
    return Episode.model_validate(data)


def test_palette_for_episode():
    from types import SimpleNamespace

    from yogen.palette import PALETTE, for_episode, text_on

    cols = for_episode(SimpleNamespace(colors=["yoko", "mura"]))
    assert [c.key for c in cols] == ["sumi", "yoko", "mura"]
    assert [c.key for c in for_episode(SimpleNamespace(colors=None))] == ["sumi", "yoko"]
    with pytest.raises(ValueError):
        for_episode(SimpleNamespace(colors=["pink"]))
    assert text_on(PALETTE["bero"].hex) == PALETTE["gofun"].hex
    assert text_on(PALETTE["too"].hex) == PALETTE["sumi"].hex


@pytest.mark.parametrize("shape", ["uroko", "hitodama", "medama"])
def test_monyou_halftone_scales_with_tone(shape):
    from yogen.halftone import monyou_halftone

    im = Image.new("RGB", (200, 100), (255, 255, 255))
    im.paste((0, 0, 0), (100, 0, 200, 100))  # 右半分が黒
    out = monyou_halftone(im, shape=shape, cell=12, ink=(0, 0, 0), paper=(255, 255, 255))

    def ink_ratio(box):
        px = list(out.crop(box).convert("L").getdata())
        return sum(1 for p in px if p < 128) / len(px)

    assert ink_ratio((110, 10, 190, 90)) > ink_ratio((10, 10, 90, 90)) + 0.2


def test_icons_render_with_cutouts():
    from yogen.icons import ICONS, stamp, svg

    for name in ICONS:
        m = stamp(name, 64)
        ink = sum(1 for v in m.getdata() if v > 128) / (64 * 64)
        assert 0.05 < ink < 0.9, name  # 空でも塗りつぶしでもない
        assert "<mask" in svg(name)
    # 達磨は顔が切り抜かれている（中心より少し上は地）
    assert stamp("daruma", 100).getpixel((50, 40)) < 128


def test_effects_produce_layers():
    from yogen.effects import chirashi, jimon, sunago, surikasane
    from yogen.icons import png

    layer = chirashi(200, 300, count=20, seed=1, avoid=(.5, .5, .2))
    assert layer.getchannel("A").getpixel((100, 150)) == 0  # 避けた円の中心は空いている
    assert layer.getbbox() is not None
    assert sunago(100, 100, density=.01).getbbox() is not None
    assert jimon(120, 80, "kingyo", 30, ground=(0, 0, 0)).size == (120, 80)
    assert surikasane(png("fuji", 40), dx=4, dy=-3).size == (44, 43)


def test_reisho_text_to_shapes():
    from yogen.calligraphy import glyph_paths, image

    d, w, h = glyph_paths("妖幻")
    assert d and (w, h) == (2000, 1000)
    d, w, h = glyph_paths("大森彦七", vertical=True)
    assert (w, h) == (1000, 4000)
    assert image("極", 64).getbbox() is not None


def test_pronunciation_fix():
    assert speakable("Welcome to YŌGEN. yogen!") == "Welcome to Yoh-gen. Yoh-gen!"


def test_upload_body_schedules_private():
    ep = sample_episode(Path("/tmp/unused"), publish_at="2099-01-01")
    body = build_body(ep, sample_script())
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2099-01-01T00:00:00Z"


def test_ass_has_brand_and_captions(tmp_path):
    s = sample_script()
    out = tmp_path / "c.ass"
    build_ass(s.beats, [2.0] * len(s.beats), out)
    text = out.read_text()
    assert "PlayResY: 1920" in text
    assert text.count("Dialogue:") == len(s.beats) + 1


def test_fact_check_gate(tmp_path, monkeypatch):
    s = sample_script()
    ep = sample_episode(tmp_path, status="scripted")
    monkeypatch.setattr(cli, "load_episode", lambda _id: ep)
    monkeypatch.setattr(cli, "load_script", lambda _id: s)
    saved = []
    monkeypatch.setattr(cli, "save_episode", saved.append)

    with pytest.raises(SystemExit):
        cli.main(["mark", "t", "fact_checked"])  # 未確認の事実が残っている

    for c in s.claims:
        c.verified = True
    cli.main(["mark", "t", "fact_checked"])
    assert saved[-1].status == Status.fact_checked


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_render_silent(tmp_path):
    ep = sample_episode(tmp_path)
    out = render_episode(ep, sample_script(), tmp_path, tts_provider="silent")
    assert out.exists() and out.stat().st_size > 10_000


def test_material_processing():
    from PIL import ImageDraw

    from yogen.materials import cutout, torn, xerox

    # 灰色のグラデーションの背景に置いた赤い物を切り抜けるか
    im = Image.new("RGB", (200, 200))
    d = ImageDraw.Draw(im)
    for y in range(200):
        d.line((0, y, 199, y), fill=(240 - y // 3,) * 3)
    d.ellipse((60, 60, 140, 140), fill=(180, 40, 40))
    c = cutout(im)
    assert c.getchannel("A").getpixel((c.width // 2, c.height // 2)) == 255
    assert c.width < 120
    x = xerox(im, paper=(0, 255, 0))
    assert x.getpixel((100, 100))[:3] != (0, 255, 0)  # 赤い円はインクになる
    assert torn(im, 8).getchannel("A").getpixel((0, 0)) == 0


def test_ink_effects():
    from yogen.inkfx import STENCIL, WIDE_BLACK, screen_print, spray, text_mask, xerox_grain

    m = text_mask("YŌGEN", WIDE_BLACK, 80)
    assert screen_print(m, (232, 179, 38)).getbbox() is not None
    s = spray(text_mask("LOOK", STENCIL, 80), (0, 0, 0))
    assert s.height > m.height  # 垂れと霧の分だけ大きい
    assert xerox_grain((60, 100)).size == (60, 100)


def test_brand_marks():
    from yogen.brand import logo_mask, wordmark_mask

    assert wordmark_mask().getbbox() is not None
    m = logo_mask()
    assert m.width > m.height  # 妖幻の横組み


def test_sticker_recipes_are_valid():
    from yogen.materials import load_index
    from yogen.stickers import recipes

    idx = load_index()
    for key, items in recipes().items():
        for r in items:
            assert r["material"] in idx, (key, r["material"])  # 出典が記録されている
            assert r["method"] in ("cutout", "key", "torn", "flood")
