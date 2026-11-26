"""yogen コマンド。

  yogen new <id> --title "..."   エピソードの雛形を作る
  yogen fetch <id>               作品画像とメタデータを取得
  yogen script <id>              Claudeで台本の下書きを作る
  yogen check <id>               事実確認の残りを表示
  yogen mark <id> <status>       状態を進める（fact_checked / approved）
  yogen render <id>              動画を作る（build/final.mp4）
  yogen publish                  approved の回を予約投稿する
  yogen status                   全エピソードの状態一覧
  yogen studio                   管理アプリと表紙のコラージュエディタを手元で開く
  yogen cover <id> [--board concept|cover]  コンセプトアート（横）かショート表紙（縦）を書き出す
  yogen collage [-n 12 --keep 3]  架空の雑誌表紙のコラージュを作り、新規性の高いものを残す
  yogen photo-collage [--seed 3]  写真だけのコラージュ（工芸品の写真で隙間なく埋める）
  yogen auth <client_secret.json> YouTube の refresh token を取得（ローカルで1回）
"""
from __future__ import annotations

import argparse
import shutil
import sys

from .config import EPISODES_DIR
from .episode import episode_dir, list_episodes, load_episode, load_script, save_episode, save_script
from .models import Status
from .sources import asset_path, fetch_artwork


def cmd_new(a):
    dest = EPISODES_DIR / a.id
    if dest.exists():
        sys.exit(f"既にあります: {dest}")
    shutil.copytree(EPISODES_DIR / "_template", dest)
    ep = load_episode(a.id)
    save_episode(ep.model_copy(update={"id": a.id, "working_title": a.title or ep.working_title}))
    print(f"作成しました: {dest}/episode.yaml を書いてください")


def ensure_assets(ep, d, force=False):
    if not force and all(asset_path(d, art.key).exists() and art.width for art in ep.artworks):
        return ep
    arts = [fetch_artwork(art, d / "assets") for art in ep.artworks]
    ep = ep.model_copy(update={"artworks": arts})
    save_episode(ep)
    return ep


def cmd_fetch(a):
    ep = ensure_assets(load_episode(a.id), episode_dir(a.id), force=True)
    for art in ep.artworks:
        print(f"  {art.key}: {art.title} / {art.artist} / {art.date} [{art.license}]")


def cmd_script(a):
    from .script import generate_script

    ep, d = load_episode(a.id), episode_dir(a.id)
    if (d / "script.yaml").exists() and not a.force:
        sys.exit("script.yaml が既にあります。作り直すなら --force")
    if not ep.research_notes.strip():
        sys.exit("research_notes が空です。一次資料のメモを先に書いてください")
    ep = ensure_assets(ep, d)
    script = generate_script(ep, d)
    save_script(a.id, script)
    save_episode(ep.model_copy(update={"status": Status.scripted}))
    print(f"台本を書きました: {d}/script.yaml")
    print(f"確認が必要な事実: {len(script.claims)} 件 → `yogen check {a.id}`")


def cmd_check(a):
    script = load_script(a.id)
    pending = [c for c in script.claims if not c.verified]
    for c in script.claims:
        print(f"  [{'x' if c.verified else ' '}] {c.claim}\n        根拠: {c.basis}")
    print(f"\n未確認 {len(pending)} / {len(script.claims)} 件")
    return pending


def cmd_mark(a):
    ep = load_episode(a.id)
    target = Status(a.status)
    if target == Status.fact_checked:
        if [c for c in load_script(a.id).claims if not c.verified]:
            sys.exit("未確認の事実があります。script.yaml の claims を一次資料で確認し verified: true にしてください")
    elif target == Status.approved:
        if ep.status != Status.fact_checked:
            sys.exit("approved にする前に fact_checked が必要です")
        if not ep.publish_at:
            sys.exit("episode.yaml に publish_at (YYYY-MM-DD) を入れてください")
    else:
        sys.exit("手で進められるのは fact_checked と approved だけです")
    save_episode(ep.model_copy(update={"status": target}))
    print(f"{a.id}: {ep.status.value} → {target.value}")


def cmd_render(a):
    from .render import render_episode

    ep, d = load_episode(a.id), episode_dir(a.id)
    ep = ensure_assets(ep, d)
    out = render_episode(ep, load_script(a.id), d, a.tts)
    print(f"書き出しました: {out}")


def cmd_publish(a):
    from .render import render_episode
    from .upload import build_body, upload_video

    targets = [e for e in list_episodes() if e.status == Status.approved and (not a.id or e.id == a.id)]
    if not targets:
        print("投稿待ち（approved）のエピソードはありません")
        return
    for ep in targets:
        d = episode_dir(ep.id)
        script = load_script(ep.id)
        if a.dry_run:
            body = build_body(ep, script)
            print(f"[dry-run] {ep.id}: {body['snippet']['title']} → {body['status']}")
            continue
        ep = ensure_assets(ep, d)
        video = render_episode(ep, script, d)
        vid = upload_video(ep, script, video)
        save_episode(ep.model_copy(update={"status": Status.scheduled, "youtube_video_id": vid}))
        print(f"{ep.id}: 予約投稿しました https://youtu.be/{vid} (公開 {ep.publish_at})")


def cmd_status(a):
    for ep in list_episodes():
        print(f"  {ep.status.value:13} {ep.publish_at or '-':10}  {ep.id}  {ep.working_title}")


def cmd_studio(a):
    from .studio.server import serve

    serve(a.host, a.port, open_browser=not a.no_open)


def cmd_cover(a):
    from .cover import check_cover, load_cover
    from .studio.server import export_cover

    ep, d = load_episode(a.id), episode_dir(a.id)
    cover = load_cover(d, a.board)
    if cover is None:
        sys.exit(f"{a.board}.yaml がありません。`yogen studio` で組んで保存してください")
    if errs := check_cover(cover, ep):
        sys.exit("ブランドの決まりに合わない層があります:\n  " + "\n  ".join(errs))
    ensure_assets(ep, d)
    for path in export_cover(d, cover, a.board):
        print(f"書き出しました: {path}")


def cmd_icons(a):
    from pathlib import Path

    from .config import ROOT
    from .icons import export

    paths = export(Path(a.dest) if a.dest else ROOT / "assets" / "icons")
    print(f"{len(paths)} 個のアイコンを書き出しました（SVG と 512px の PNG）")


def cmd_collage(a):
    from .collage import generate

    recs = generate(a.n, a.keep, a.out, a.seed, a.min_aesthetic)
    print(f"{len(recs)} 枚を {a.out} に残しました")


def cmd_photo_collage(a):
    from pathlib import Path

    from .photo_collage import generate

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    img, st = generate(a.seed)
    path = out / f"photo_{a.seed}.png"
    img.save(path)
    print(f"{path}: 物 {st['objects']} 個＋主役 {st['heroes']}  埋まり {st['covered']*100:.1f}%  墨のまま {st['bare']*100:.1f}%")


def cmd_auth(a):
    from .upload import run_oauth_flow

    run_oauth_flow(a.client_secret)


def main(argv=None):
    p = argparse.ArgumentParser(prog="yogen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new"); s.add_argument("id"); s.add_argument("--title"); s.set_defaults(f=cmd_new)
    s = sub.add_parser("fetch"); s.add_argument("id"); s.set_defaults(f=cmd_fetch)
    s = sub.add_parser("script"); s.add_argument("id"); s.add_argument("--force", action="store_true"); s.set_defaults(f=cmd_script)
    s = sub.add_parser("check"); s.add_argument("id"); s.set_defaults(f=cmd_check)
    s = sub.add_parser("mark"); s.add_argument("id"); s.add_argument("status", choices=["fact_checked", "approved"]); s.set_defaults(f=cmd_mark)
    s = sub.add_parser("render"); s.add_argument("id"); s.add_argument("--tts", choices=["silent", "elevenlabs"]); s.set_defaults(f=cmd_render)
    s = sub.add_parser("publish"); s.add_argument("--id"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_publish)
    s = sub.add_parser("status"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("studio"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true"); s.set_defaults(f=cmd_studio)
    s = sub.add_parser("cover"); s.add_argument("id"); s.add_argument("--board", choices=["concept", "cover"], default="concept")
    s.set_defaults(f=cmd_cover)
    s = sub.add_parser("icons"); s.add_argument("--dest"); s.set_defaults(f=cmd_icons)
    s = sub.add_parser("collage"); s.add_argument("-n", type=int, default=12); s.add_argument("--keep", type=int, default=3)
    s.add_argument("--out", default="out/collage"); s.add_argument("--seed", type=int); s.add_argument("--min-aesthetic", type=float, default=.55)
    s.set_defaults(f=cmd_collage)
    s = sub.add_parser("photo-collage"); s.add_argument("--seed", type=int, default=3); s.add_argument("--out", default="out/photo")
    s.set_defaults(f=cmd_photo_collage)
    s = sub.add_parser("auth"); s.add_argument("client_secret"); s.set_defaults(f=cmd_auth)

    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
