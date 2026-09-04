#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mixkit 免费素材采集（免登录直链）。

解析分类页卡片（id + 标题），按 assets.mixkit.co 的 id 模式构造直链
（720p 默认；--quality 1080 时逐条 HEAD 校验 1080，失败回落 720）。
素材为 Mixkit Restricted License，可免费用于商业/个人视频。

Usage:
  python collect_mixkit.py --category game --pages 2 \
      --out mixkit.json --csv mixkit.csv
  python collect_mixkit.py --category game --quality 1080 --limit 30 --out mixkit.json
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import requests

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CATEGORIES = ["game", "backgrounds", "sports", "nature", "city", "people",
              "animals", "food", "travel", "music", "business", "abstract"]
TITLE_RE = re.compile(
    r"item-grid-video-player__overlay-video-title\">\s*([^<]+?)\s*<", re.S)
HREF_RE = re.compile(
    r'class="item-grid-video-player__overlay-link"\s+href="(/free-stock-video/[^"]+)"')


def fetch_category(session, category, page):
    url = f"https://mixkit.co/free-stock-video/{category}/"
    if page > 1:
        url += f"?page={page}"
    r = session.get(url, headers={"User-Agent": UA}, timeout=25)
    r.raise_for_status()
    return r.text


def parse_cards(text):
    """解析分类页卡片：id + 标题 + 详情页链接。"""
    items = []
    for seg in text.split('data-algolia-analytics-object-id="video-')[1:]:
        vid = seg[: seg.find('"')]
        if not vid.isdigit():
            continue
        title_m = TITLE_RE.search(seg)
        href_m = HREF_RE.search(seg)
        if not title_m and not href_m:
            continue
        items.append({
            "id": vid,
            "title": title_m.group(1).strip() if title_m else "",
            "page_url": ("https://mixkit.co" + href_m.group(1)) if href_m else "",
        })
    return items


def resolve_quality(session, vid, want):
    """按 id 模式构造直链；1080 用 HEAD 校验，失败回落 720。"""
    base = f"https://assets.mixkit.co/videos/{vid}/{vid}"
    cands = ([f"{base}-1080.mp4", f"{base}-720.mp4"] if want >= 1080
             else [f"{base}-720.mp4"])
    for u in cands:
        try:
            r = session.head(u, headers={"User-Agent": UA}, timeout=10)
            if r.status_code == 200:
                return u
        except requests.RequestException:
            pass
    return f"{base}-720.mp4"


def main():
    ap = argparse.ArgumentParser(description="Mixkit 免登录素材采集")
    ap.add_argument("--category", default="game",
                    help=f"分类，可选：{', '.join(CATEGORIES)}")
    ap.add_argument("--pages", type=int, default=1, help="抓取页数（默认 1，每页 24 条）")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--quality", type=int, default=720,
                    help="目标清晰度：720（默认）/ 1080（逐条 HEAD 校验，稍慢）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="mixkit.json")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    if args.category not in CATEGORIES:
        print(f"分类不在预设列表，仍尝试抓取：{args.category}")
    session = requests.Session()
    seen, videos = set(), []
    for page in range(1, max(1, args.pages) + 1):
        text = fetch_category(session, args.category, page)
        rows = parse_cards(text)
        if not rows:
            print(f"  第{page}页没有内容，停止", flush=True)
            break
        added = 0
        for c in rows:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            url = resolve_quality(session, c["id"], args.quality)
            videos.append({
                "title": c["title"],
                "url": url,
                "page_url": c["page_url"],
            })
            added += 1
        print(f"  第{page}页 {len(rows)} 条，新增 {added}，累计 {len(videos)}", flush=True)
        if args.limit and len(videos) >= args.limit:
            videos = videos[: args.limit]
            break
        if page < args.pages:
            time.sleep(args.delay)

    result = {"source": "mixkit", "category": args.category,
              "count": len(videos), "videos": videos}
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"Mixkit[{args.category}] 采集 {len(videos)} 条，已写入 {out}")
    for v in videos[:8]:
        print(f"  {v['title'][:44]} | {v['url'].split('/')[-1]}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["title", "url", "page_url"])
            for v in videos:
                w.writerow([csv_cell(v["title"]), v["url"], v["page_url"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
