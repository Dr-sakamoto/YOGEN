from __future__ import annotations

from pathlib import Path

import yaml

from .config import EPISODES_DIR
from .models import Episode, Script


def episode_dir(episode_id: str) -> Path:
    d = EPISODES_DIR / episode_id
    if not d.is_dir():
        raise SystemExit(f"エピソードが見つかりません: {d}")
    return d


def load_episode(episode_id: str) -> Episode:
    with open(episode_dir(episode_id) / "episode.yaml", encoding="utf-8") as f:
        return Episode.model_validate(yaml.safe_load(f))


def save_episode(ep: Episode) -> None:
    _dump(ep.model_dump(mode="json"), EPISODES_DIR / ep.id / "episode.yaml")


def load_script(episode_id: str) -> Script:
    path = episode_dir(episode_id) / "script.yaml"
    if not path.exists():
        raise SystemExit(f"台本がありません。先に `yogen script {episode_id}` を実行してください")
    with open(path, encoding="utf-8") as f:
        return Script.model_validate(yaml.safe_load(f))


def save_script(episode_id: str, script: Script) -> None:
    _dump(script.model_dump(mode="json"), EPISODES_DIR / episode_id / "script.yaml")


def list_episodes() -> list[Episode]:
    eps = []
    for d in sorted(EPISODES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "episode.yaml").exists():
            eps.append(load_episode(d.name))
    return eps


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, s: str):
    # 改行を含む文字列は | ブロックで書き、人が編集しやすくする
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None)


_Dumper.add_representer(str, _str)


def _dump(data: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)
