#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download Bilibili videos via yt-dlp and normalize to h264/aac MP4.

Accept a BVID / official URL / list file / search JSON. Anonymous access
yields up to 720p; 1080p and higher need login cookies (--cookies).

Security hardening (2026-09-04):
- Only pure BV ids or https://www.bilibili.com/video/BV... official URLs are
  accepted; "-"-prefixed lines are rejected (prevents yt-dlp option injection);
- Output identifiers always come from the BV regex, so path traversal via
  input URLs is not possible.

Usage:
  python download_bilibili.py --url BV1px411o7jN --out-dir materials/witcher
  python download_bilibili.py --list-file urls.txt --quality 720 --limit 5 --out-dir materials
  python download_bilibili.py --search-json bilibili_search.json --limit 3 --out-dir materials/demo
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 可留空：yt_dlp 已装到当前 Python 环境时无需额外配置；也可用 YTDLP_CMD 指定可执行文件。
PYTHON_LIBS = []
FFMPEG_PATHS = []
BV_RE = re.compile(r"^(BV[0-9A-Za-z]{10})$")
BILI_URL_RE = re.compile(r"^https://www\.bilibili\.com/video/(BV[0-9A-Za-z]{10})(?:[/?#]|$)")


def find_ffmpeg():
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    for p in FFMPEG_PATHS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 ffmpeg：请加入 PATH 或设置 FFMPEG 环境变量")


def ytdlp_cmd():
    """Return (argv, libdir) for a working yt-dlp invocation."""
    env_cmd = os.environ.get("YTDLP_CMD")
    if env_cmd:
        return env_cmd.split(), None
    if shutil.which("yt-dlp"):
        return ["yt-dlp"], None
    python = sys.executable
    for lib in PYTHON_LIBS:
        if os.path.isdir(os.path.join(lib, "yt_dlp")):
            return [python, "-m", "yt_dlp"], lib
    raise SystemExit("未找到 yt-dlp：设置 YTDLP_CMD 或安装 yt_dlp 包")


def to_official_url(raw):
    """只接受纯 BV 号或官方 bilibili URL，返回规范化官方 URL；其余返回 None。"""
    t = raw.strip()
    if t.startswith("-"):  # 防 yt-dlp 选项注入
        return None
    if BV_RE.match(t):
        return "https://www.bilibili.com/video/" + t
    m = BILI_URL_RE.match(t)
    if m:
        return "https://www.bilibili.com/video/" + m.group(1)
    return None


def bvid_of(official_url):
    """从已校验的官方 URL 取 BV 号（恒为安全字符）。"""
    m = BILI_URL_RE.match(official_url)
    return m.group(1) if m else None


def run(cmd, libdir=None, timeout=3600):
    env = dict(os.environ)
    if libdir:
        env["PYTHONPATH"] = libdir + (os.pathsep + env["PYTHONPATH"]
                                      if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout)


def collect_targets(args):
    targets = []
    if args.url:
        targets.extend(args.url)
    if args.list_file:
        with open(args.list_file, "r", encoding="utf-8-sig") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    targets.append(ln)
    if args.search_json:
        with open(args.search_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        for v in data.get("videos", []):
            bvid = (v.get("bvid") or "").strip()
            if BV_RE.match(bvid):
                targets.append(bvid)
            else:
                print(f"  ! 跳过非法 bvid: {bvid[:80]}")
    seen = []
    for raw in targets:
        official = to_official_url(raw)  # 拒绝 - 开头行/非官方 URL
        if official is None:
            print(f"  ! 跳过非法目标: {raw[:80]}")
            continue
        if official not in seen:
            seen.append(official)
    return seen[: args.limit] if args.limit else seen


def normalize_video(src, out_path):
    ffmpeg = find_ffmpeg()
    r = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", src,
         "-c:v", "libx264", "-crf", "19", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out_path],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=3600)
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def main():
    ap = argparse.ArgumentParser(description="B 站批量下载（yt-dlp + ffmpeg 规范化）")
    ap.add_argument("--url", action="append", default=None, help="BV 号或完整链接（可多次）")
    ap.add_argument("--list-file", default=None, help="每行一个 BV/链接的清单文件")
    ap.add_argument("--search-json", default=None, help="search_bilibili.py 输出的 JSON")
    ap.add_argument("--quality", type=int, default=720, choices=[360, 480, 720, 1080],
                    help="目标清晰度（匿名最高 720；1080 需登录 Cookie）")
    ap.add_argument("--out-dir", default="materials", help="输出目录")
    ap.add_argument("--limit", type=int, default=0, help="最多下载条数")
    ap.add_argument("--cookies", default=None, help="Netscape cookies 文件（1080p/会员画质）")
    ap.add_argument("--cookies-from-browser", default=None,
                    help="从浏览器读登录态：chrome / edge / firefox（1080p/会员画质）")
    ap.add_argument("--section", default=None, help="只下载片段，如 0-15（秒）")
    ap.add_argument("--no-normalize", action="store_true", help="下载后不做 ffmpeg 规范化")
    args = ap.parse_args()

    targets = collect_targets(args)
    if not targets:
        raise SystemExit("没有可下载的目标：提供 --url / --list-file / --search-json")

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    base, libdir = ytdlp_cmd()
    fmt = (f"bv*[height<={args.quality}]+ba/b[height<={args.quality}]/b")
    manifest = []
    for i, t in enumerate(targets, 1):
        bvid = bvid_of(t) or t
        print(f"[{i}/{len(targets)}] 下载 {bvid} ...")
        cmd = base + ["--no-warnings", "--write-info-json",
                      "-f", fmt, "--merge-output-format", "mp4",
                      "-o", os.path.join(out_dir, bvid, bvid + ".%(ext)s")]
        if args.cookies:
            cmd += ["--cookies", args.cookies]
        elif args.cookies_from_browser:
            cmd += ["--cookies-from-browser", args.cookies_from_browser]
        if args.section:
            cmd += ["--download-sections", f"*{args.section}"]
        r = run(cmd + [t], libdir=libdir)
        if r.returncode != 0:
            print(f"  ✗ 下载失败: {(r.stderr or r.stdout)[-400:].strip()}")
            continue
        # locate downloaded media inside the per-bvid folder
        folder = os.path.join(out_dir, bvid)
        media = None
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    media = os.path.join(folder, f)
                    break
        if not media:
            print("  ✗ 未找到下载产物")
            continue
        final = os.path.join(out_dir, bvid + ".mp4")
        if args.no_normalize:
            if os.path.abspath(media) != os.path.abspath(final):
                shutil.copy2(media, final)
        elif not normalize_video(media, final):
            print("  ✗ 规范化失败，保留原文件")
            final = media
        size_mb = os.path.getsize(final) / 1024 / 1024
        manifest.append({"bvid": bvid, "file": os.path.abspath(final), "size_mb": round(size_mb, 1)})
        print(f"  ✓ {os.path.basename(final)} ({size_mb:.1f} MB)")

    man_path = os.path.join(out_dir, "download_manifest.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(manifest), "files": manifest}, f, ensure_ascii=False, indent=1)
    print(f"完成 {len(manifest)}/{len(targets)}，清单: {man_path}")


if __name__ == "__main__":
    main()
