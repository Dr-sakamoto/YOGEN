"""台本から縦型ショート（1080x1920）を作る。

1. 作品ごとに縦長キャンバスを作る（ぼかした背景＋作品全体）
2. ビートごとに zoompan でズーム・パンし、ナレーション音声と合わせる
3. つないで、ASS字幕とロゴを焼き込み、必要ならBGMを混ぜる

毎回カメラワークが入るので、静止画スライドショーには見えない
（企画書「収益化ポリシーと権利のリスク対策」）。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter

from .config import channel_config
from .models import Beat, Episode, Script
from .sources import asset_path
from .tts import synthesize

SCALE = 2  # キャンバスは出力の2倍。zoompan のガタつきを抑える


@dataclass
class Canvas:
    path: Path
    fx: int  # 作品が置かれた矩形（キャンバス座標）
    fy: int
    fw: int
    fh: int
    cw: int
    ch: int


def build_canvas(src: Path, dest: Path, out_w: int, out_h: int) -> Canvas:
    cw, ch = out_w * SCALE, out_h * SCALE
    with Image.open(src) as im:
        im = im.convert("RGB")
        # 背景: 画面を覆うように拡大してぼかし、暗くする
        r = max(cw / im.width, ch / im.height)
        bg = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        left, top = (bg.width - cw) // 2, (bg.height - ch) // 2
        bg = bg.crop((left, top, left + cw, top + ch)).filter(ImageFilter.GaussianBlur(40))
        bg = Image.eval(bg, lambda v: int(v * 0.45))
        # 前景: 作品全体が収まるように
        f = min(cw / im.width, ch / im.height)
        fw, fh = int(im.width * f), int(im.height * f)
        fg = im.resize((fw, fh), Image.LANCZOS)
        fx, fy = (cw - fw) // 2, (ch - fh) // 2
        bg.paste(fg, (fx, fy))
        dest.parent.mkdir(parents=True, exist_ok=True)
        bg.save(dest, quality=95)
    return Canvas(dest, fx, fy, fw, fh, cw, ch)


def zoompan_filter(beat: Beat, canvas: Canvas, frames: int, out_w: int, out_h: int, fps: int) -> str:
    s = beat.shot
    cx = canvas.fx + s.focus_x * canvas.fw
    cy = canvas.fy + s.focus_y * canvas.fh
    n = max(frames - 1, 1)
    # なめらかに動かすため ease-in-out
    t = f"(0.5-0.5*cos(PI*on/{n}))"
    z = f"{s.zoom_start}+({s.zoom_end}-{s.zoom_start})*{t}"
    # 窓が作品より小さいときは作品の内側に収め、大きいときは作品全体を含むようにする
    # （作品の外のぼかし背景にカメラが逸れないように）
    def axis(c: float, a0: int, alen: int, full: str) -> str:
        win = f"{full}/zoom"
        lo = f"min({a0}\\,{a0 + alen}-{win})"
        hi = f"max({a0}\\,{a0 + alen}-{win})"
        return f"clip(clip({c:.1f}-{win}/2\\,{lo}\\,{hi})\\,0\\,{full}-{win})"

    x = axis(cx, canvas.fx, canvas.fw, "iw")
    y = axis(cy, canvas.fy, canvas.fh, "ih")
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={out_w}x{out_h}:fps={fps}"


def _run(cmd: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd], check=True)


def _ass_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_text(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def build_ass(beats: list[Beat], durations: list[float], dest: Path) -> None:
    cfg = channel_config()
    r = cfg["render"]
    font = r["font"]
    total = sum(durations)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {r['width']}",
        f"PlayResY: {r['height']}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,5,2,2,80,80,420,1",
        f"Style: Hook,{font},84,&H0000E6FF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,6,2,5,80,80,0,1",
        f"Style: Brand,{font},44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,6,0,1,3,0,8,40,40,110,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,{_ass_time(0)},{_ass_time(total)},Brand,,0,0,0,,"
        f"{cfg['channel']['name']}  {cfg['channel']['kanji']}",
    ]
    t = 0.0
    for beat, d in zip(beats, durations):
        style = "Hook" if beat.role == "hook" else "Caption"
        lines.append(
            f"Dialogue: 1,{_ass_time(t)},{_ass_time(t + d)},{style},,0,0,0,,{_ass_text(beat.caption)}"
        )
        t += d
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_episode(ep: Episode, script: Script, ep_dir: Path, tts_provider: str | None = None) -> Path:
    r = channel_config()["render"]
    W, H, fps = r["width"], r["height"], r["fps"]
    build = ep_dir / "build"
    build.mkdir(exist_ok=True)

    canvases = {
        a.key: build_canvas(asset_path(ep_dir, a.key), build / f"canvas_{a.key}.jpg", W, H)
        for a in ep.artworks
    }

    clips, durations = [], []
    for i, beat in enumerate(script.beats):
        audio = build / f"vo_{i:02d}.mp3"
        dur = synthesize(beat.narration, audio, tts_provider) + 0.25  # 文間の間
        frames = int(round(dur * fps))
        durations.append(frames / fps)
        clip = build / f"clip_{i:02d}.mp4"
        vf = zoompan_filter(beat, canvases[beat.shot.artwork], frames, W, H, fps)
        _run([
            "-i", str(canvases[beat.shot.artwork].path), "-i", str(audio),
            "-filter_complex", f"[0:v]{vf},format=yuv420p[v];[1:a]apad,atrim=0:{frames / fps:.3f}[a]",
            "-map", "[v]", "-map", "[a]", "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", str(clip),
        ])
        clips.append(clip)

    concat_list = build / "concat.txt"
    concat_list.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    joined = build / "joined.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)])

    ass = build / "captions.ass"
    build_ass(script.beats, durations, ass)

    final = build / "final.mp4"
    inputs = ["-i", str(joined)]
    vf = f"[0:v]ass={ass.as_posix()}[v]"
    if r.get("bgm"):
        inputs += ["-stream_loop", "-1", "-i", r["bgm"]]
        af = "[1:a]volume=0.12[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        af = "[0:a]anull[a]"
    _run([
        *inputs, "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
    ])
    return final
