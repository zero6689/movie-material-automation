#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B站素材 API 下载器（备用，绕过 yt-dlp 412 风控）。

view API 拿 cid/标题 → playurl 拿 720p 直链 → ffmpeg 下载并规范化为 MP4。

Security hardening (2026-09-04):
- 只接受纯 BV 号或 https://www.bilibili.com/video/BV... 官方 URL；
- BV 号经正则提取后才用于文件名/目录，杜绝路径穿越与 yt-dlp 选项注入。

Usage:
  python download_api.py --list-file urls.txt --out-dir materials
  python download_api.py --url https://www.bilibili.com/video/BVxxx --out-dir materials
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
FFMPEG_PATHS = []  # ffmpeg 通过 PATH 或 FFMPEG 环境变量查找
BV_RE = re.compile(r"^(BV[0-9A-Za-z]{10})$")
BILI_URL_RE = re.compile(r"^https://www\.bilibili\.com/video/(BV[0-9A-Za-z]{10})(?:[/?#]|$)")


def find_ffmpeg():
    exe = os.environ.get("FFMPEG")
    if exe and os.path.exists(exe):
        return exe
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in FFMPEG_PATHS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 ffmpeg：请加入 PATH 或设置 FFMPEG 环境变量")


def extract_bvid(raw):
    """从输入提取合法 BV 号；不合法返回 None。"""
    t = raw.strip()
    if not t or t.startswith("-"):
        return None
    if BV_RE.match(t):
        return t
    m = BILI_URL_RE.match(t)
    if m:
        return m.group(1)
    return None


def anonymous_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    buvid3 = str(uuid.uuid4()).upper() + "infoc"
    fp = hashlib.md5(buvid3.encode()).hexdigest()
    for k, v in {
        "buvid3": buvid3,
        "buvid4": str(uuid.uuid4()).upper() + "infoc",
        "buvid_fp": buvid3,
        "fingerprint": fp,
        "b_nut": str(int(time.time())),
        "_uuid": "EB5655BE-F2BE-AF5B-D2F6-49C8F97AA5C714739infoc",
        "b_lsid": "A76B9B18_1834ED4D5AE",
        "sid": "8p4mof00",
        "innersign": "0",
    }.items():
        s.cookies.set(k, v, domain=".bilibili.com")
    return s


def get_playurl(session, bvid):
    r = session.get("https://api.bilibili.com/x/web-interface/view",
                    params={"bvid": bvid}, timeout=20)
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"view 失败 code={d.get('code')} {d.get('message')}")
    info = d["data"]
    cid = info["cid"]
    r2 = session.get("https://api.bilibili.com/x/player/playurl",
                     params={"bvid": bvid, "cid": cid, "qn": 64,
                             "fnval": 1, "fnver": 0, "fourk": 0}, timeout=20)
    d2 = r2.json()
    if d2.get("code") != 0:
        raise RuntimeError(f"playurl 失败 code={d2.get('code')} {d2.get('message')}")
    data = d2["data"]
    durl = data.get("durl")
    if not durl:
        raise RuntimeError("无视频流")
    return {
        "bvid": bvid,
        "cid": cid,
        "title": info.get("title", bvid),
        "author": (info.get("owner") or {}).get("name", ""),
        "duration": info.get("duration", 0),
        "quality": data.get("quality"),
        "url": durl[0]["url"],
        "format": data.get("format"),
    }


def download(session, bvid, out_dir, quality_720=True):
    info = get_playurl(session, bvid)
    os.makedirs(out_dir, exist_ok=True)
    out_mp4 = os.path.join(out_dir, f"{bvid}.mp4")
    if os.path.exists(out_mp4):
        print(f"  已存在: {os.path.basename(out_mp4)}，跳过")
        return info
    tmp = out_mp4 + ".part.mp4"
    ffmpeg = find_ffmpeg()
    headers = (
        f"Referer: https://www.bilibili.com/\r\n"
        f"User-Agent: {UA}\r\n"
    )
    # try remux first (fast); fall back to re-encode
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-headers", headers, "-i", info["url"], "-c", "copy",
           "-movflags", "+faststart", tmp]
    r = subprocess.run(cmd)
    if r.returncode != 0 and os.path.exists(tmp):
        os.remove(tmp)
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-headers", headers, "-i", info["url"],
               "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", tmp]
        subprocess.run(cmd, check=True)
    os.replace(tmp, out_mp4)
    with open(os.path.join(out_dir, f"{bvid}.info.json"), "w",
              encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    size = os.path.getsize(out_mp4) / 1e6
    print(f"  OK {bvid} 「{info['title'][:30]}」 {info['duration']}s "
          f"{size:.1f}MB")
    return info


def main():
    ap = argparse.ArgumentParser(description="B站 API 下载器")
    ap.add_argument("--url")
    ap.add_argument("--list-file")
    ap.add_argument("--out-dir", default="materials")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    bvids = []
    if args.url:
        b = extract_bvid(args.url)
        if b:
            bvids = [b]
        else:
            print(f"  ! 跳过非法目标: {args.url[:80]}")
    elif args.list_file:
        with open(args.list_file, "r", encoding="utf-8") as f:
            for line in f:
                b = extract_bvid(line)
                if b:
                    bvids.append(b)
                elif line.strip():
                    print(f"  ! 跳过非法目标: {line.strip()[:80]}")
    if not bvids:
        raise SystemExit("需要 --url 或 --list-file")
    if args.limit:
        bvids = bvids[: args.limit]

    session = anonymous_session()
    manifest = []
    for i, bv in enumerate(bvids, 1):
        print(f"[{i}/{len(bvids)}] 下载 {bv} ...", flush=True)
        try:
            info = download(session, bv, args.out_dir)
            manifest.append(info)
        except Exception as e:
            print(f"  ✗ {bv} 失败: {e}")
        time.sleep(2)
    with open(os.path.join(args.out_dir, "api_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"完成 {len(manifest)}/{len(bvids)}，清单: "
          f"{os.path.join(args.out_dir, 'api_manifest.json')}")


if __name__ == "__main__":
    main()
