from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
EPISODES_DIR = ROOT / "episodes"
PROMPTS_DIR = ROOT / "prompts"


@lru_cache
def channel_config() -> dict[str, Any]:
    with open(ROOT / "config" / "channel.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
