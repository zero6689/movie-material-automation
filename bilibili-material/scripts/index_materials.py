#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scan a material folder and build a searchable media index.

Merges yt-dlp sidecar *.info.json (bvid/title/uploader/duration) with ffprobe
measurements and writes index.json + index.csv.

Usage:
  python index_materials.py --dir materials --out index.json
  python index_materials.py --dir materials --tag witcher --csv index.csv
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


FFPROBE_PATHS = []  # ffprobe 通过 PATH 或 FFPROBE 环境变量查找


def ffprobe():
    exe = os.environ.get("FFPROBE") or shutil.which("ffprobe")
    if exe:
        return exe
    for p in FFPROBE_PATHS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 ffprobe：请加入 PATH 或设置 FFPROBE 环境变量")


def probe(path):
    r = subprocess.run([ffprobe(), "-v", "error",
                        "-show_entries", "format=duration:stream=width,height",
                        "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    try:
        d = json.loads(r.stdout)
    except Exception:
        return None, None
    dur = None
    try:
        dur = float(d["format"]["duration"])
    except Exception:
        pass
    w = h = None
    for st in d.get("streams", []):
        if st.get("width") and st.get("height"):
            w, h = st["width"], st["height"]
            break
    return dur, (f"{w}x{h}" if w and h else None)


def load_info_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "bvid": d.get("bvid") or d.get("id"),
            "title": d.get("title"),
            "uploader": (d.get("uploader") or {}).get("uploader")
                        or d.get("uploader"),
            "duration": d.get("duration"),
        }
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description="素材目录索引")
    ap.add_argument("--dir", required=True, help="素材目录（递归扫描 mp4/mkv/webm）")
    ap.add_argument("--out", default="index.json", help="输出 JSON")
    ap.add_argument("--csv", default=None, help="可选 CSV")
    ap.add_argument("--tag", default="", help="素材标签")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    entries = []
    for dirpath, _, files in os.walk(root):
        info = {}
        for f in files:
            if f.endswith(".info.json"):
                info = load_info_json(os.path.join(dirpath, f))
                break
        for f in sorted(files):
            if not f.endswith((".mp4", ".mkv", ".webm")):
                continue
            path = os.path.join(dirpath, f)
            dur, res = probe(path)
            entries.append({
                "file": path,
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
                "duration": round(dur, 1) if dur else None,
                "resolution": res,
                "bvid": info.get("bvid"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "tag": args.tag,
            })
    entries.sort(key=lambda x: x["file"])
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"count": len(entries), "dir": root, "entries": entries},
                  f, ensure_ascii=False, indent=1)
    print(f"共索引 {len(entries)} 个素材文件 → {out}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "title", "bvid", "uploader", "duration",
                        "resolution", "size_mb", "tag"])
            for e in entries:
                w.writerow([e["file"], e["title"], e["bvid"], e["uploader"],
                            e["duration"], e["resolution"], e["size_mb"], e["tag"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
