"""エピソードと台本のデータ構造。

1本の動画 = episodes/<id>/ の1ディレクトリ。
  episode.yaml  … 人が書く企画・リサーチメモ・状態
  script.yaml   … Claudeが下書きし、人が直す台本
  assets/       … 取得した作品画像（git管理外）
  build/        … 音声・字幕・完成動画（git管理外）
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Status(str, Enum):
    draft = "draft"                # 企画・リサーチ中
    scripted = "scripted"          # 台本の下書きができた
    fact_checked = "fact_checked"  # 人が固有名詞・年代・出典を確認した
    approved = "approved"          # 人が試写して投稿OKを出した
    scheduled = "scheduled"        # YouTubeに予約投稿済み
    published = "published"


# 人の確認を経ないと進めない状態
HUMAN_GATES = {Status.fact_checked, Status.approved}


class Artwork(BaseModel):
    key: str = Field(description="台本から参照する短い名前（例: main, detail2）")
    source: Literal["met", "aic", "local"]
    object_id: str | None = None
    local_path: str | None = None

    # fetch で埋まる
    title: str | None = None
    artist: str | None = None
    date: str | None = None
    image_url: str | None = None
    page_url: str | None = None
    credit: str | None = None
    license: str | None = None
    is_public_domain: bool | None = None
    width: int | None = None
    height: int | None = None


class Episode(BaseModel):
    id: str
    status: Status = Status.draft
    working_title: str
    artworks: list[Artwork]
    research_notes: str = Field(description="人が一次資料から書いたメモ。台本の事実はここからだけ取る")
    sources: list[str] = Field(default_factory=list, description="伝承・解説の出典")
    publish_at: str | None = Field(default=None, description="予約公開日 YYYY-MM-DD")
    colors: list[str] | None = Field(
        default=None, description="その回の4色（墨は固定）を手で選ぶとき。palette.py のキー（bero, yoko …）"
    )
    youtube_video_id: str | None = None
    review_notes: str = ""


# ---- 台本（Claudeの構造化出力） ----

class Shot(BaseModel):
    artwork: str = Field(description="Artwork.key")
    focus_x: float = Field(ge=0, le=1, description="注目点の横位置（作品画像の左端0〜右端1）")
    focus_y: float = Field(ge=0, le=1, description="注目点の縦位置（上端0〜下端1）")
    zoom_start: float = Field(ge=1, le=6, description="開始時の拡大率。1=作品全体")
    zoom_end: float = Field(ge=1, le=6, description="終了時の拡大率")


class Beat(BaseModel):
    role: Literal["hook", "story", "wide", "landing"] = Field(
        description="hook=0-3秒の謎, story=伝承・正体, wide=引きで美術史, landing=社会・死生観への着地"
    )
    narration: str = Field(description="英語ナレーション。1文〜3文")
    caption: str = Field(description="画面に出す短い英語字幕（narrationの要約可）")
    shot: Shot


class Claim(BaseModel):
    claim: str = Field(description="台本中の事実主張（固有名詞・年代・出典を含むもの）")
    basis: str = Field(description="research_notes / sources のどこに基づくか")
    verified: bool = Field(default=False, description="人が一次資料で確認したらtrueにする")


class Script(BaseModel):
    title: str = Field(description="YouTubeタイトル（英語, 70字以内, #Shorts は付けない）")
    description: str = Field(description="説明文（英語）。作品名・絵師・年・所蔵先を含める")
    tags: list[str]
    beats: list[Beat]
    claims: list[Claim]
