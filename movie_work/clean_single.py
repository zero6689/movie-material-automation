# -*- coding: utf-8 -*-
"""单文件清洗：crop-top N + 放大回原尺寸 + setsar=1，音轨 copy 保留。"""
import argparse
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
_FFMPEG_FALLBACK = r"V:\CodexProjects\.tools\ffmpeg\bin\ffmpeg.exe"
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or _FFMPEG_FALLBACK


def probe_size(video):
    import re
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", video],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in out.stderr.splitlines():
        if "Video:" in line and "x" in line:
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return 1280, 720


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop-top", type=int, required=True)
    args = ap.parse_args()
    w, h = probe_size(args.src)
    top = args.crop_top if args.crop_top % 2 == 0 else args.crop_top + 1
    if top >= h:
        raise SystemExit(f"裁剪过大: top={top} h={h}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    filt = f"crop={w}:{h - top}:0:{top},scale={w}:{h},setsar=1"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", args.src, "-vf", filt, "-c:v", "libx264", "-crf", "17",
                    "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", args.out], check=True)
    print(f"清洗完成: {os.path.basename(args.src)} crop_top={top} -> {args.out}")


if __name__ == "__main__":
    main()
