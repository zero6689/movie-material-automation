#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YouTube 关键词搜索（yt-dlp ytsearch，免 API key）。

需要能访问 YouTube 的网络（本机走 VPN 时，采集命令需在宿主网络下运行）。
部分视频/网络会触发 YouTube 的“Sign in to confirm you’re not a bot”，
此时加 --cookies（用 Get cookies.txt LOCALLY 导出 youtube.com 的登录 Cookie）。

Usage:
  python search_youtube.py --keyword "elden ring 战斗" --limit 10 \
      --out youtube.json --csv youtube.csv
  python search_youtube.py --keyword-file kw.txt --cookies youtube_cookies.txt \
      --limit 20 --out youtube.json
"""
import argparse
import csv
import json
import os
import subprocess
import sys

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


PYTHON_LIBS = [r"V:\CodexProjects\witcher-world\python-libs"]


def ytdlp_cmd():
    env_cmd = os.environ.get("YTDLP_CMD")
    if env_cmd:
        return env_cmd.split(), None
    if os.environ.get("PYTHONPATH") or any(
            os.path.isdir(os.path.join(lib, "yt_dlp")) for lib in PYTHON_LIBS):
        return [sys.executable, "-m", "yt_dlp"], PYTHON_LIBS
    return [sys.executable, "-m", "yt_dlp"], None


def run(cmd, libdirs=None, timeout=180):
    env = dict(os.environ)
    if libdirs:
        env["PYTHONPATH"] = os.pathsep.join(libdirs) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, capture_output=True, env=env, timeout=timeout)


def search(keyword, limit, cookies=None):
    base, libdirs = ytdlp_cmd()
    cmd = base + ["--flat-playlist", "--dump-single-json", "--no-warnings",
                  f"ytsearch{max(1, limit)}:{keyword}"]
    if cookies:
        cmd += ["--cookies", cookies]
    p = run(cmd, libdirs=libdirs)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or b"").decode("utf-8", "replace")
        raise SystemExit(f"YouTube 搜索失败：{err[-400:]}")
    data = json.loads((p.stdout or b"").decode("utf-8", "replace"))
    videos = []
    for e in data.get("entries", []):
        vid = e.get("id")
        if not vid:
            continue
        videos.append({
            "id": vid,
            "title": e.get("title") or "",
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": int(e.get("duration") or 0),
            "view_count": int(e.get("view_count") or 0),
            "upload_date": e.get("upload_date") or "",
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return videos


def main():
    ap = argparse.ArgumentParser(description="YouTube 关键词搜索")
    ap.add_argument("--keyword", default=None)
    ap.add_argument("--keyword-file", default=None, help="UTF-8 关键词文件")
    ap.add_argument("--limit", type=int, default=10, help="搜索条数（默认 10）")
    ap.add_argument("--cookies", default=None, help="youtube.com 的 cookies.txt（风控时必填）")
    ap.add_argument("--out", default="youtube_search.json")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    keyword = args.keyword
    if args.keyword_file:
        with open(args.keyword_file, "r", encoding="utf-8-sig") as f:
            keyword = f.read().strip()
    if not keyword:
        raise SystemExit("请提供 --keyword 或 --keyword-file")

    videos = search(keyword, args.limit, args.cookies)
    result = {
        "source": "youtube",
        "query": keyword,
        "count": len(videos),
        "videos": videos,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"YouTube 搜索「{keyword}」共 {len(videos)} 条，已写入 {out}")
    for v in videos[:10]:
        print(f"  {v['id']} {v['title'][:40]} | {v['channel'][:18]} | {v['duration']}s")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "title", "channel", "duration", "view_count", "url"])
            for v in videos:
                w.writerow([v["id"], v["title"], v["channel"], v["duration"],
                            v["view_count"], v["url"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
