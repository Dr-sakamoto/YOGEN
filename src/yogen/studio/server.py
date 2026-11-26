"""yogen studio：運営管理アプリとコラージュエディタ（手元で起動するローカルサーバー）。

  /                         エピソード一覧（状態・事実確認の残り・公開日・表紙）
  /#/cover/<id>             表紙のコラージュエディタ

表紙は episodes/<id>/cover.yaml に保存するので、ふだんの git・PR の流れに乗る。
状態（fact_checked / approved）はここでは進めない。人が `yogen mark` で進める。
"""
from __future__ import annotations

import io
import json
import mimetypes
import re
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml
from PIL import Image
from pydantic import ValidationError

from .. import cover as cv
from ..config import EPISODES_DIR, ROOT, channel_config
from ..episode import list_episodes, load_episode
from ..palette import PALETTE, for_episode
from ..sources import asset_path

STATIC = Path(__file__).parent / "static"
STICKER_PNG = ROOT / "assets" / "stickers"
PIPELINE = ["draft", "scripted", "fact_checked", "approved", "scheduled", "published"]
_lock = threading.Lock()  # 網点づくりと保存は1本ずつ


def _episode_ids() -> set[str]:
    return {e.id for e in list_episodes()}


def _claims(ep_dir: Path) -> dict | None:
    p = ep_dir / "script.yaml"
    if not p.exists():
        return None
    claims = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("claims") or []
    return {"total": len(claims), "verified": sum(1 for c in claims if c.get("verified"))}


def episode_summary(ep) -> dict:
    d = EPISODES_DIR / ep.id
    return {
        "id": ep.id,
        "title": ep.working_title,
        "status": ep.status.value,
        "publish_at": ep.publish_at,
        "colors": [c.key for c in for_episode(ep)[1:]],
        "claims": _claims(d),
        "has_cover": cv.cover_path(d).exists(),
        "artworks_ready": all(asset_path(d, a.key).exists() for a in ep.artworks),
        "youtube_video_id": ep.youtube_video_id,
    }


def episode_detail(ep) -> dict:
    d = EPISODES_DIR / ep.id
    cover = cv.load_cover(d)
    out = episode_summary(ep)
    out.update({
        "artworks": [
            {"key": a.key, "title": a.title, "artist": a.artist, "date": a.date, "license": a.license,
             "width": a.width, "height": a.height, "ready": asset_path(d, a.key).exists()}
            for a in ep.artworks
        ],
        "cover": (cover or cv.default_cover(ep)).model_dump(mode="json"),
        "cover_saved": cover is not None,
    })
    return out


def parts() -> dict:
    from ..stickers import recipes

    W, H = cv.canvas_size()
    stickers = []
    for key, rs in recipes().items():
        for i, r in enumerate(rs):
            stickers.append({"key": key, "index": i, "note": r.get("note", ""),
                             "thumb": f"/assets/stickers/{key}_{i}.png"
                             if (STICKER_PNG / f"{key}_{i}.png").exists() else None})
    return {
        "canvas": {"width": W, "height": H},
        "palette": {k: {"name": c.name, "hex": c.hex} for k, c in PALETTE.items()},
        "stickers": stickers,
        "fonts": cv.fonts(),
        "halftone_width": cv.HALFTONE_WIDTH,
        "channel": channel_config()["channel"],
        "pipeline": PIPELINE,
    }


def _png(im: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    im.save(buf, fmt, **({"quality": 88} if fmt == "JPEG" else {}))
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "yogen-studio"

    def log_message(self, fmt, *args):  # 静かに
        pass

    # ---- 応答 ----
    def _send(self, body: bytes, ctype: str, status: int = 200, cache: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200):
        self._send(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def _error(self, status: int, msg: str, **extra):
        self._json({"error": msg, **extra}, status)

    def _file(self, path: Path, cache: bool = True):
        if not path.is_file():
            return self._error(404, f"ありません: {path.name}")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(path.read_bytes(), ctype, cache=cache)

    def _episode(self, eid: str):
        if eid not in _episode_ids():
            self._error(404, f"エピソードが見つかりません: {eid}")
            return None
        return load_episode(eid)

    # ---- ルーティング ----
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path
        try:
            if p in ("/", "/index.html"):
                return self._file(STATIC / "index.html", cache=False)
            if m := re.fullmatch(r"/static/([\w.-]+)", p):
                return self._file(STATIC / m[1], cache=False)
            if m := re.fullmatch(r"/fonts/(.+\.ttf)", p):
                if m[1] not in cv.fonts():
                    return self._error(404, "フォントがありません")
                return self._file(cv.FONTS_DIR / m[1])
            if m := re.fullmatch(r"/assets/stickers/([\w]+_\d+\.png)", p):
                return self._file(STICKER_PNG / m[1])
            if p == "/api/episodes":
                return self._json([episode_summary(e) for e in list_episodes()])
            if p == "/api/parts":
                return self._json(parts())
            if m := re.fullmatch(r"/api/episodes/([\w-]+)", p):
                if ep := self._episode(m[1]):
                    return self._json(episode_detail(ep))
                return
            if m := re.fullmatch(r"/api/episodes/([\w-]+)/artwork/([\w-]+)\.jpg", p):
                if ep := self._episode(m[1]):
                    if m[2] not in {a.key for a in ep.artworks}:
                        return self._error(404, "作品がありません")
                    return self._file(asset_path(EPISODES_DIR / ep.id, m[2]))
                return
            if m := re.fullmatch(r"/api/episodes/([\w-]+)/cover\.(png|jpg)", p):
                if ep := self._episode(m[1]):
                    d = EPISODES_DIR / ep.id
                    cover = cv.load_cover(d) or cv.default_cover(ep)
                    return self._render(cover, d, m[2], q)
                return
            if m := re.fullmatch(r"/api/part/sticker/([\w]+)/(\d+)/(gofun|sumi)\.png", p):
                from ..stickers import recipes

                if m[1] not in recipes() or int(m[2]) >= len(recipes()[m[1]]):
                    return self._error(404, "素材がありません")
                with _lock:
                    im = cv.sticker_part(m[1], int(m[2]), m[3])
                return self._send(_png(im), "image/png", cache=True)
            if m := re.fullmatch(r"/api/part/logo/(gofun|sumi)\.png", p):
                with _lock:
                    im = cv.logo_part(m[1])
                return self._send(_png(im), "image/png", cache=True)
            if p == "/api/part/wordmark.png":
                with _lock:
                    im = cv.wordmark_part()
                return self._send(_png(im), "image/png", cache=True)
            return self._error(404, "ありません")
        except BrokenPipeError:
            pass
        except Exception as e:  # エディタに理由を見せる
            self._error(500, f"{type(e).__name__}: {e}")

    def _render(self, cover: cv.Cover, d: Path, fmt: str, q: dict):
        width = int(q.get("w", ["0"])[0] or 0)
        with _lock:
            try:
                im = cv.render_cover(cover, d)
            except FileNotFoundError as e:
                return self._error(409, str(e))
        if width and width < im.width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        if fmt == "jpg":
            return self._send(_png(im, "JPEG"), "image/jpeg")
        return self._send(_png(im), "image/png")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _cover_from_body(self, ep):
        try:
            cover = cv.Cover.model_validate(self._body())
        except (ValidationError, json.JSONDecodeError) as e:
            self._error(422, "表紙のデータが読めません", detail=str(e))
            return None
        if errs := cv.check_cover(cover, ep):
            self._error(422, "ブランドの決まりに合わない層があります", problems=errs)
            return None
        return cover

    def do_PUT(self):
        try:
            if m := re.fullmatch(r"/api/episodes/([\w-]+)/cover", urlparse(self.path).path):
                if (ep := self._episode(m[1])) and (cover := self._cover_from_body(ep)):
                    with _lock:
                        path = cv.save_cover(EPISODES_DIR / ep.id, cover)
                    return self._json({"saved": _rel(path)})
                return
            self._error(404, "ありません")
        except Exception as e:
            self._error(500, f"{type(e).__name__}: {e}")

    def do_POST(self):
        u = urlparse(self.path)
        try:
            # 保存せずに今の状態を書き出して見る（エディタの「たしかめる」）
            if m := re.fullmatch(r"/api/episodes/([\w-]+)/preview\.jpg", u.path):
                if (ep := self._episode(m[1])) and (cover := self._cover_from_body(ep)):
                    return self._render(cover, EPISODES_DIR / ep.id, "jpg", parse_qs(u.query))
                return
            if m := re.fullmatch(r"/api/episodes/([\w-]+)/export", u.path):
                if ep := self._episode(m[1]):
                    d = EPISODES_DIR / ep.id
                    cover = cv.load_cover(d)
                    if cover is None:
                        return self._error(409, "先に表紙を保存してください")
                    with _lock:
                        try:
                            path = export_cover(d, cover)
                        except FileNotFoundError as e:
                            return self._error(409, str(e))
                    return self._json({"exported": _rel(path)})
                return
            self._error(404, "ありません")
        except Exception as e:
            self._error(500, f"{type(e).__name__}: {e}")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def export_cover(ep_dir: Path, cover: cv.Cover) -> Path:
    out = ep_dir / "build" / "cover.png"
    out.parent.mkdir(exist_ok=True)
    cv.render_cover(cover, ep_dir).save(out)
    return out


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"yogen studio: {url}  （止めるときは Ctrl+C）")
    if open_browser:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n止めました")
    finally:
        httpd.server_close()
