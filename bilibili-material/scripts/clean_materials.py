#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Detect watermark / burned-in subtitles in downloaded clips and clean them.

Watermark check: top-right corner edge density vs frame middle.
Subtitle check: bottom band edge density.
Cleaning: crop the top band (watermark) and scale back to original size.

Usage:
  python clean_materials.py --dir materials --report report.json
  python clean_materials.py --dir materials --crop-top 44 --out-dir clean/
  python clean_materials.py --dir materials --report r.json --crop-top 44 --out-dir clean/
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from PIL import Image

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
if not FFMPEG:
    raise SystemExit("未找到 ffmpeg：请加入 PATH 或设置 FFMPEG 环境变量")
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".ts", ".m4s"}


def probe_size(video):
    out = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", video],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in out.stderr.splitlines():
        if "Video:" in line and "x" in line:
            import re
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return 1280, 720


def frame_edge_stats(video, t):
    tmp = os.path.join(os.path.dirname(video) or ".", "_wm_tmp.png")
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", tmp],
                   check=True)
    a = np.asarray(Image.open(tmp).convert("L")).astype(float)
    os.remove(tmp)
    h, w = a.shape
    tr = a[:int(h * 0.10), int(w * 0.78):]
    mid = a[int(h * 0.45):int(h * 0.55), int(w * 0.45):int(w * 0.55)]
    bot = a[int(h * 0.86):, :]
    grad = lambda x: float(np.abs(np.diff(x, axis=1)).mean())
    return {
        "tr_grad": grad(tr), "mid_grad": grad(mid), "bot_grad": grad(bot),
        "tr_ratio": grad(tr) / max(0.01, grad(mid)),
        "bot_ratio": grad(bot) / max(0.01, grad(mid)),
        "tr_std": float(tr.std()),
    }


def analyze(video, samples=3):
    import subprocess as sp
    dur = 60.0
    out = sp.run([FFMPEG, "-hide_banner", "-i", video],
                 capture_output=True, text=True, encoding="utf-8",
                 errors="replace")
    for line in out.stderr.splitlines():
        if "Duration:" in line and ":" in line:
            try:
                parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                dur = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            except Exception:
                pass
            break
    stats = [frame_edge_stats(video, dur * (i + 1) / (samples + 1))
             for i in range(samples)]
    # 取最大值：水印/字幕全程存在，任一帧命中即标记
    return {k: max(s[k] for s in stats) for k in stats[0]}


def main():
    ap = argparse.ArgumentParser(description="素材水印/字幕检测与清洗")
    ap.add_argument("--dir", required=True, help="素材目录")
    ap.add_argument("--report", help="输出检测报告 JSON")
    ap.add_argument("--crop-top", type=int, help="裁掉顶部 N 像素（去水印）并放大回原尺寸")
    ap.add_argument("--out-dir", help="清洗输出目录（需 --crop-top）")
    ap.add_argument("--subtitle-ratio", type=float, default=3.0,
                    help="底部字幕判定阈值（底部/中部边缘密度比）")
    ap.add_argument("--watermark-ratio", type=float, default=1.8,
                    help="右上水印判定阈值")
    args = ap.parse_args()

    files = sorted(
        os.path.join(args.dir, f) for f in os.listdir(args.dir)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTS)
    if not files:
        raise SystemExit(f"目录里没有视频: {args.dir}")

    report = []
    for v in files:
        s = analyze(v)
        watermark = s["tr_ratio"] >= args.watermark_ratio and s["tr_std"] > 25
        subtitle = s["bot_ratio"] >= args.subtitle_ratio
        report.append({
            "file": os.path.abspath(v),
            "size": f"{probe_size(v)[0]}x{probe_size(v)[1]}",
            "watermark_suspect": bool(watermark),
            "subtitle_suspect": bool(subtitle),
            "tr_ratio": round(s["tr_ratio"], 2),
            "bot_ratio": round(s["bot_ratio"], 2),
            "tr_std": round(s["tr_std"], 1),
        })
        flag = []
        if watermark:
            flag.append("水印?")
        if subtitle:
            flag.append("字幕?")
        print(f"{os.path.basename(v)}: " + ("、".join(flag) if flag else "干净"))

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"报告: {args.report}")

    if args.crop_top:
        if not args.out_dir:
            raise SystemExit("需要 --out-dir 与 --crop-top 一起使用")
        os.makedirs(args.out_dir, exist_ok=True)
        for v in files:
            w, h = probe_size(v)
            top = args.crop_top if args.crop_top % 2 == 0 else args.crop_top + 1
            if top >= h:
                print(f"跳过 {os.path.basename(v)}（裁剪过大）")
                continue
            dst = os.path.join(args.out_dir, os.path.basename(v))
            filt = f"crop={w}:{h - top}:0:{top},scale={w}:{h}"
            subprocess.run(
                [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                 "-i", v, "-vf", filt, "-c:v", "libx264", "-crf", "17",
                 "-preset", "medium", "-pix_fmt", "yuv420p",
                 "-c:a", "copy", dst], check=True)
            print(f"清洗: {os.path.basename(v)} -> {dst}")


if __name__ == "__main__":
    main()
