#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Search Bilibili videos by keyword and export a filterable list.

Uses the public search API with an anonymous fingerprint cookie set
(no login required). Chinese keywords work; pass them via --keyword-file
when the shell encoding is unreliable.

Usage:
  python search_bilibili.py --keyword "巫师3 战斗" --out videos.json
  python search_bilibili.py --keyword-file kw.txt --pages 3 --order totalrank --out videos.json
  python search_bilibili.py --keyword "鬼泣5" --min-duration 120 --max-duration 1800 \
      --min-play 10000 --min-danmaku 100 --limit 50 --csv videos.csv
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import uuid

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


import requests

SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TAG_RE = re.compile(r"<[^>]+>")


def anonymous_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    buvid3 = str(uuid.uuid4()).upper() + "infoc"
    fp = hashlib.md5(buvid3.encode()).hexdigest()
    for k, v in {
        "buvid3": buvid3,
        "buvid4": buvid3,
        "buvid_fp": buvid3,
        "buvid_fp_plain": "undefined",
        "fingerprint": fp,
        "b_nut": str(int(time.time())),
        "_uuid": "EB5655BE-F2BE-AF5B-D2F6-49C8F97AA5C714739infoc",
        "b_lsid": "A76B9B18_1834ED4D5AE",
        "sid": "8p4mof00",
        "innersign": "0",
    }.items():
        s.cookies.set(k, v, domain=".bilibili.com")
    return s


def clean_title(t):
    return TAG_RE.sub("", t or "").strip()


def parse_duration(v):
    if isinstance(v, (int, float)):
        return int(v)
    parts = str(v or "0").split(":")
    try:
        if len(parts) == 1:
            return int(float(parts[0]))
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


def search(session, keyword, page=1, order=None):
    params = {"search_type": "video", "keyword": keyword, "page": page}
    if order:
        params["order"] = order
    r = session.get(SEARCH_URL, params=params, timeout=20)
    d = r.json()
    if d.get("code") != 0:
        raise SystemExit(f"搜索失败 code={d.get('code')} msg={d.get('message')}")
    return d.get("data") or {}


def normalize(v):
    return {
        "bvid": v.get("bvid"),
        "aid": v.get("aid"),
        "title": clean_title(v.get("title")),
        "author": v.get("author"),
        "duration": parse_duration(v.get("duration")),
        "play": int(v.get("play") or 0),
        "danmaku": int(v.get("video_review") or 0),
        "pubdate": int(v.get("pubdate") or 0),
        "description": (v.get("description") or "")[:200],
        "cover": v.get("pic") or "",
        "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
    }


def main():
    ap = argparse.ArgumentParser(description="B 站关键词搜索")
    ap.add_argument("--keyword", default=None, help="搜索关键词")
    ap.add_argument("--keyword-file", default=None, help="从 UTF-8 文件读取关键词（推荐中文）")
    ap.add_argument("--out", default="bilibili_search.json", help="输出 JSON")
    ap.add_argument("--csv", default=None, help="可选 CSV 输出")
    ap.add_argument("--pages", type=int, default=1, help="抓取页数（默认 1）")
    ap.add_argument("--order", default=None,
                    choices=["totalrank", "click", "pubdate", "dm", "score"],
                    help="排序：综合/播放/最新/弹幕/评分")
    ap.add_argument("--min-duration", type=int, default=0, help="最短时长（秒）")
    ap.add_argument("--max-duration", type=int, default=0, help="最长时长（秒）")
    ap.add_argument("--min-play", type=int, default=0, help="最低播放量")
    ap.add_argument("--min-danmaku", type=int, default=0, help="最低弹幕数")
    ap.add_argument("--limit", type=int, default=0, help="最多保留条数（0=不限）")
    args = ap.parse_args()

    keyword = args.keyword
    if args.keyword_file:
        with open(args.keyword_file, "r", encoding="utf-8-sig") as f:
            keyword = f.read().strip()
    if not keyword:
        raise SystemExit("请提供 --keyword 或 --keyword-file")

    session = anonymous_session()
    seen, videos = set(), []
    for page in range(1, args.pages + 1):
        data = search(session, keyword, page=page, order=args.order)
        for v in data.get("result") or []:
            item = normalize(v)
            if not item["bvid"] or item["bvid"] in seen:
                continue
            seen.add(item["bvid"])
            if args.min_duration and item["duration"] < args.min_duration:
                continue
            if args.max_duration and item["duration"] > args.max_duration:
                continue
            if args.min_play and item["play"] < args.min_play:
                continue
            if args.min_danmaku and item["danmaku"] < args.min_danmaku:
                continue
            videos.append(item)
            if args.limit and len(videos) >= args.limit:
                break
        if args.limit and len(videos) >= args.limit:
            break
        if not data.get("result"):
            break

    result = {
        "query": keyword,
        "order": args.order or "totalrank",
        "count": len(videos),
        "videos": videos,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"关键词「{keyword}」共 {len(videos)} 条，已写入 {out}")
    for v in videos[:10]:
        print(f"  {v['bvid']} {v['title'][:34]} | {v['duration']}s | 播放 {v['play']} | 弹幕 {v['danmaku']}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bvid", "title", "author", "duration", "play",
                        "danmaku", "pubdate", "url"])
            for v in videos:
                w.writerow([v["bvid"], v["title"], v["author"], v["duration"],
                            v["play"], v["danmaku"], v["pubdate"], v["url"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
