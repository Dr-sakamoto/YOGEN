"""Claude API で台本の下書きを作る。"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import anthropic
from PIL import Image

from .config import PROMPTS_DIR, channel_config
from .models import Episode, Script
from .sources import asset_path


def _image_block(path: Path) -> dict:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((1568, 1568))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buf.getvalue()).decode(),
        },
    }


def system_prompt() -> str:
    cfg = channel_config()
    target = cfg["script"]["target_seconds"]
    words = int(target * cfg["script"]["words_per_second"])
    tmpl = (PROMPTS_DIR / "script_system.md").read_text(encoding="utf-8")
    return tmpl.format(
        target_seconds=target,
        words=words,
        pronunciation=cfg["channel"]["pronunciation"],
    )


def build_user_content(ep: Episode, ep_dir: Path) -> list[dict]:
    content: list[dict] = []
    for art in ep.artworks:
        content.append({"type": "text", "text": f"Artwork `{art.key}`:"})
        content.append(_image_block(asset_path(ep_dir, art.key)))
    meta = [a.model_dump(include={"key", "title", "artist", "date", "credit", "page_url"}) for a in ep.artworks]
    content.append({
        "type": "text",
        "text": (
            f"Working title: {ep.working_title}\n\n"
            f"Artwork metadata:\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n\n"
            f"Research notes (written by a human from primary sources):\n{ep.research_notes}\n\n"
            f"Sources:\n" + "\n".join(f"- {s}" for s in ep.sources) + "\n\n"
            "Write the script."
        ),
    })
    return content


def generate_script(ep: Episode, ep_dir: Path) -> Script:
    cfg = channel_config()["script"]
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=cfg["model"],
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": cfg["effort"]},
        system=system_prompt(),
        messages=[{"role": "user", "content": build_user_content(ep, ep_dir)}],
        output_format=Script,
    )
    if response.stop_reason == "refusal":
        detail = response.stop_details.explanation if response.stop_details else ""
        raise RuntimeError(f"台本生成が拒否されました: {detail}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"台本を取得できませんでした (stop_reason={response.stop_reason})")

    script = response.parsed_output
    keys = {a.key for a in ep.artworks}
    bad = [b.shot.artwork for b in script.beats if b.shot.artwork not in keys]
    if bad:
        raise RuntimeError(f"台本が存在しない作品キーを参照しています: {bad}")
    return script
