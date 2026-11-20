"""ナレーション音声。provider を差し替えられるようにしておく。

silent     … APIキーなしで尺だけ見積もった無音を作る（試写・CI用）
elevenlabs … ElevenLabs の音声合成
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import requests

from .config import channel_config

# 英語TTSは「ヨージェン」と読みがち。音声用テキストだけ綴りを変える（企画書「発音対策」）
PRONUNCIATION_FIXES = [(re.compile(r"\bY[ŌO]GEN\b", re.IGNORECASE), "Yoh-gen")]


def speakable(text: str) -> str:
    for pat, rep in PRONUNCIATION_FIXES:
        text = pat.sub(rep, text)
    return text


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def estimate_seconds(text: str) -> float:
    wps = channel_config()["script"]["words_per_second"]
    return max(1.5, len(text.split()) / wps + 0.4)


def _silent(text: str, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{estimate_seconds(text):.2f}", "-c:a", "libmp3lame", "-q:a", "4", str(dest)],
        check=True,
    )


def _elevenlabs(text: str, dest: Path) -> None:
    cfg = channel_config()["tts"]
    voice = cfg["elevenlabs_voice_id"]
    if not voice:
        raise SystemExit("config/channel.yaml の tts.elevenlabs_voice_id を設定してください")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": speakable(text), "model_id": cfg["elevenlabs_model"]},
        timeout=120,
    )
    r.raise_for_status()
    dest.write_bytes(r.content)


def synthesize(text: str, dest: Path, provider: str | None = None) -> float:
    """音声を dest に書き出し、秒数を返す。"""
    provider = provider or channel_config()["tts"]["provider"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    {"silent": _silent, "elevenlabs": _elevenlabs}[provider](text, dest)
    return probe_duration(dest)
