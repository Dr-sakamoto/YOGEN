"""YouTube Data API v3 で予約投稿する。

いきなり公開はしない。privacyStatus=private + publishAt で予約し、
公開時刻にYouTube側が自動で公開する。
"""
from __future__ import annotations

import os
from datetime import datetime, time, timezone
from pathlib import Path

from .config import channel_config
from .models import Episode, Script

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def credentials():
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )


def publish_at_rfc3339(date_str: str) -> str:
    hour = channel_config()["upload"]["publish_hour_utc"]
    d = datetime.combine(datetime.fromisoformat(date_str).date(), time(hour), tzinfo=timezone.utc)
    if d <= datetime.now(timezone.utc):
        raise SystemExit(f"publish_at {date_str} は過去です。未来の日付にしてください")
    return d.isoformat().replace("+00:00", "Z")


def build_body(ep: Episode, script: Script) -> dict:
    up = channel_config()["upload"]
    status = {
        "privacyStatus": up["default_privacy"],
        "selfDeclaredMadeForKids": up["made_for_kids"],
        "containsSyntheticMedia": up["contains_synthetic_media"],
    }
    if ep.publish_at:
        status["privacyStatus"] = "private"  # publishAt は private のときだけ有効
        status["publishAt"] = publish_at_rfc3339(ep.publish_at)
    return {
        "snippet": {
            "title": script.title[:100],
            "description": script.description,
            "tags": script.tags,
            "categoryId": up["category_id"],
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }


def upload_video(ep: Episode, script: Script, video: Path) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    req = yt.videos().insert(
        part="snippet,status",
        body=build_body(ep, script),
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        _, response = req.next_chunk()
    return response["id"]


def run_oauth_flow(client_secret_file: str) -> None:
    """ローカルで一度だけ実行し、refresh token を表示する。"""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("GitHub の Secrets に以下を登録してください:")
    print(f"  YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"  YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    print(f"  YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
