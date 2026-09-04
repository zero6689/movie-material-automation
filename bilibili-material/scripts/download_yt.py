#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YouTube / Twitch 通用下载器（yt-dlp + ffmpeg 规范化成 h264/aac MP4）。

需要能访问 YouTube/Twitch 的网络（本机走 VPN 时，采集命令需在宿主网络下运行）。
YouTube 遇风控（Sign in to confirm you’re not a bot）时加 --cookies；
Twitch 片段/回放直接传 clip 或 VOD 链接即可。

Security hardening (2026-09-04):
- 只接受 https:// 且主机在允许名单（youtube/youtu.be/twitch/acfun/ixigua）内的 URL；
- "-"-前缀行与非 https URL 直接拒绝（防 yt-dlp 选项注入）；
- 输出 id 用正则限制字符集，杜绝路径穿越。

Usage:
  python download_yt.py --search-json youtube_search.json --limit 3 --out-dir materials/yt
  python download_yt.py --url "https://www.youtube.com/watch?v=xxx" --out-dir materials/yt
  python download_yt.py --list-file clips.txt --cookies youtube_cookies.txt --out-dir materials/yt
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PYTHON_LIBS = []  # 可留空：yt_dlp 装在当前 Python 环境或由 YTDLP_CMD 指定
FFMPEG_PATHS = []  # ffmpeg 通过 PATH 或 FFMPEG 环境变量查找
ALLOWED_HOSTS = ("youtube.com", "youtu.be", "twitch.tv",
                 "acfun.cn", "ixigua.com")
ID_RE = re.compile(r"^[0-9A-Za-z_-]{2,64}$")
YT_V_RE = re.compile(r"[?&]v=([0-9A-Za-z_-]{6,})")


def find_ffmpeg():
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    for p in FFMPEG_PATHS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 ffmpeg：请加入 PATH 或设置 FFMPEG 环境变量")


def ytdlp_cmd():
    env_cmd = os.environ.get("YTDLP_CMD")
    if env_cmd:
        return env_cmd.split(), None
    if shutil.which("yt-dlp"):
        return ["yt-dlp"], None
    return [sys.executable, "-m", "yt_dlp"], PYTHON_LIBS


def run(cmd, libdirs=None, timeout=7200):
    env = dict(os.environ)
    if libdirs:
        env["PYTHONPATH"] = os.pathsep.join(libdirs) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, capture_output=True, env=env, timeout=timeout)


def is_allowed_url(t):
    """https + 主机白名单校验；返回规范化 URL 或 None。"""
    s = t.strip()
    if not s.startswith("https://"):
        return None
    try:
        u = urllib.parse.urlparse(s)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        return None
    return s


def video_id(url):
    """从白名单 URL 提取安全 id；失败返回 None。"""
    m = YT_V_RE.search(url)
    if m:
        return m.group(1)
    path = urllib.parse.urlparse(url).path.rstrip("/")
    last = path.split("/")[-1] if path else ""
    return last if last and ID_RE.match(last) else None


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
            if v.get("url"):
                targets.append(v["url"])
            elif v.get("id"):
                # 仅 youtube 类搜索产物允许裸 id（安全字符集）
                if ID_RE.match(str(v["id"])) and ID_RE.fullmatch(str(v["id"])):
                    targets.append("https://www.youtube.com/watch?v=" + str(v["id"]))
    seen = []
    for raw in targets:
        if raw.strip().startswith("-"):
            print(f"  ! 拒绝疑似选项输入: {raw[:60]}")
            continue
        ok = is_allowed_url(raw)
        if ok is None:
            print(f"  ! 跳过非法目标（需 https + 白名单域名）: {raw[:80]}")
            continue
        if ok not in seen:
            seen.append(ok)
    return seen[: args.limit] if args.limit else seen


def normalize_video(src, out_path):
    ffmpeg = find_ffmpeg()
    r = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", src,
         "-c:v", "libx264", "-crf", "19", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out_path],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=7200)
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def parse_section(spec):
    """'0-15' -> (0, 15)；解析失败返回 (None, None)。"""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$", spec)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def main():
    ap = argparse.ArgumentParser(description="YouTube/Twitch 通用下载（yt-dlp + ffmpeg 规范化）")
    ap.add_argument("--url", action="append", default=None, help="视频/clip 链接（可多次）")
    ap.add_argument("--list-file", default=None, help="每行一个链接的清单文件")
    ap.add_argument("--search-json", default=None, help="search_youtube.py 输出的 JSON")
    ap.add_argument("--quality", type=int, default=1080,
                    help="目标高度（默认 1080；部分视频匿名只能 720 及以下）")
    ap.add_argument("--out-dir", default="materials")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cookies", default=None, help="Netscape cookies.txt（YouTube 风控/高画质）")
    ap.add_argument("--cookies-from-browser", default=None,
                    help="chrome / edge / firefox（读浏览器登录态）")
    ap.add_argument("--section", default=None, help="只下载片段，如 0-15（秒）")
    ap.add_argument("--no-normalize", action="store_true", help="下载后不做 ffmpeg 规范化")
    args = ap.parse_args()

    targets = collect_targets(args)
    if not targets:
        raise SystemExit("没有可下载的目标：提供 --url / --list-file / --search-json")

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    base, libdirs = ytdlp_cmd()
    fmt = (f"bv*[height<={args.quality}]+ba/b[height<={args.quality}]/b")
    ffmpeg = None
    try:
        ffmpeg = find_ffmpeg()
    except SystemExit:
        pass
    manifest = []
    for i, t in enumerate(targets, 1):
        vid = video_id(t)
        if vid is None:
            print(f"  ! 无法提取安全 id，跳过: {t[:80]}")
            continue
        print(f"[{i}/{len(targets)}] 下载 {vid} ...")
        cmd = base + ["--no-warnings", "--write-info-json",
                      "-f", fmt, "--merge-output-format", "mp4",
                      "-o", os.path.join(out_dir, vid, vid + ".%(ext)s")]
        if ffmpeg:
            cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg)]
        if args.cookies:
            cmd += ["--cookies", args.cookies]
        elif args.cookies_from_browser:
            cmd += ["--cookies-from-browser", args.cookies_from_browser]
        if args.section:
            cmd += ["--download-sections", f"*{args.section}"]
        section_fallback = False
        r = run(cmd + [t], libdirs=libdirs)
        if r.returncode != 0:
            if args.section:
                print("  --section 下载失败，改下完整视频再本地切割")
                section_fallback = True
                r = run([c for c in cmd if c != "--download-sections"] + [t],
                        libdirs=libdirs)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or b"").decode("utf-8", "replace")
                print(f"  ✗ 下载失败: {err[-300:].strip()}")
                continue

        folder = os.path.join(out_dir, vid)
        media = None
        info = {}
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    media = os.path.join(folder, f)
                elif f.endswith(".info.json"):
                    try:
                        with open(os.path.join(folder, f), "r", encoding="utf-8") as fj:
                            info = json.load(fj)
                    except Exception:
                        pass
        if not media:
            print("  ✗ 未找到下载产物")
            continue
        if section_fallback and args.section and ffmpeg:
            start, end = parse_section(args.section)
            if start is not None:
                cut = media + ".cut.mp4"
                rc = subprocess.run(
                    [ffmpeg, "-y", "-v", "error", "-ss", str(start),
                     "-to", str(end), "-i", media, "-c", "copy", cut],
                    capture_output=True, timeout=1800).returncode
                if rc == 0 and os.path.exists(cut) and os.path.getsize(cut) > 0:
                    media = cut

        final = os.path.join(out_dir, vid + ".mp4")
        if args.no_normalize:
            if os.path.abspath(media) != os.path.abspath(final):
                shutil.copy2(media, final)
        elif not normalize_video(media, final):
            print("  ✗ 规范化失败，保留原文件")
            final = media
        size_mb = os.path.getsize(final) / 1024 / 1024
        manifest.append({
            "id": vid,
            "title": info.get("title", vid),
            "channel": info.get("channel") or info.get("uploader") or "",
            "duration": int(info.get("duration") or 0),
            "url": info.get("webpage_url", t),
            "file": os.path.abspath(final),
            "size_mb": round(size_mb, 1),
        })
        print(f"  ✓ {os.path.basename(final)} ({size_mb:.1f} MB)")

    man_path = os.path.join(out_dir, "download_manifest.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(manifest), "files": manifest},
                  f, ensure_ascii=False, indent=1)
    print(f"完成 {len(manifest)}/{len(targets)}，清单: {man_path}")


if __name__ == "__main__":
    main()
