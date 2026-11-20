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


def test_palette_from_pigments(tmp_path):
    from yogen.palette import GOFUN, SUMI, extract, text_on

    im = Image.new("RGB", (300, 300), (215, 204, 171))  # 紙の地
    im.paste((60, 90, 140), (0, 0, 300, 90))            # 藍
    im.paste((170, 60, 55), (100, 150, 200, 250))       # 紅
    im.save(tmp_path / "p.jpg")
    pal = extract(tmp_path / "p.jpg")
    r, g, b = (int(pal.shu[i:i + 2], 16) for i in (1, 3, 5))
    assert b > r  # 主色は藍から
    r, g, b = (int(pal.sashi[i:i + 2], 16) for i in (1, 3, 5))
    assert r > b  # 差し色は紅から
    assert text_on("#c4ab42") == SUMI and text_on("#2c4359") == GOFUN


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
    assert jimon(120, 80, "ume", 30, ground=(0, 0, 0)).size == (120, 80)
    assert surikasane(png("fuji", 40), dx=4, dy=-3).size == (44, 43)


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
