#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A站（AcFun）关键词搜索（匿名可用，BigPipe quickView 接口）。

Usage:
  python search_acfun.py --keyword "巫师3 战斗" --pages 2 \
      --out acfun.json --csv acfun.csv
  python search_acfun.py --keyword-file kw.txt --limit 30 --out acfun.json
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse

import requests

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
SPLITTER = "/*<!-- fetch-stream -->*/"
EXPOSURE_RE = re.compile(r"data-exposure-log='(\{.*?\})'", re.S)
DUR_RE = re.compile(r"video__duration\">([^<]+)<")
USER_RE = re.compile(r"user-name\">([^<]+)<")
VIEW_RE = re.compile(r"info__view-count\">([^<]+)<")
DATE_RE = re.compile(r"info__create-time\">([^<]+)<")
URL_RE = re.compile(r'href="(/v/ac\d+)"')


def parse_duration(s):
    parts = str(s or "").strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


def parse_view(s):
    m = re.search(r"([\d.]+)\s*万", s or "")
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)", s or "")
    return int(m.group(1)) if m else 0


def fetch_page(session, keyword, page):
    k = urllib.parse.quote(keyword)
    url = ("https://www.acfun.cn/search?keyword=" + k +
           "&quickViewId=video-list&reqID=0&ajaxpipe=1&sortType=0"
           "&channelId=&type=video")
    if page > 1:
        url += f"&page={page}"
    url += "&keyword=" + k
    r = session.get(url, headers={
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.acfun.cn/search?keyword=" + k,
    }, timeout=25)
    r.raise_for_status()
    return r.text


def parse_response(text):
    html_parts = []
    for chunk in text.split(SPLITTER):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            d = json.loads(chunk)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("html"):
            html_parts.append(d["html"])
    html = "".join(html_parts)
    videos = []
    for seg in html.split('class="search-video"')[1:]:
        m = EXPOSURE_RE.search(seg)
        if not m:
            continue
        try:
            meta = json.loads(m.group(1))
        except ValueError:
            continue
        vid = meta.get("content_id")
        if not vid:
            continue
        title = meta.get("title") or ""
        url_m = URL_RE.search(seg)
        dur_m = DUR_RE.search(seg)
        user_m = USER_RE.search(seg)
        view_m = VIEW_RE.search(seg)
        date_m = DATE_RE.search(seg)
        videos.append({
            "id": f"ac{vid}",
            "title": title,
            "author": user_m.group(1).strip() if user_m else "",
            "duration": parse_duration(dur_m.group(1)) if dur_m else 0,
            "view_count": parse_view(view_m.group(1)) if view_m else 0,
            "pubdate": date_m.group(1).strip() if date_m else "",
            "url": ("https://www.acfun.cn" + url_m.group(1)) if url_m
                   else f"https://www.acfun.cn/v/ac{vid}",
        })
    return videos


def main():
    ap = argparse.ArgumentParser(description="A站关键词搜索（匿名）")
    ap.add_argument("--keyword", default=None)
    ap.add_argument("--keyword-file", default=None)
    ap.add_argument("--pages", type=int, default=1, help="抓取页数（默认 1，每页约 20 条）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.5, help="翻页间隔秒数")
    ap.add_argument("--out", default="acfun_search.json")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    keyword = args.keyword
    if args.keyword_file:
        with open(args.keyword_file, "r", encoding="utf-8-sig") as f:
            keyword = f.read().strip()
    if not keyword:
        raise SystemExit("请提供 --keyword 或 --keyword-file")

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    seen, videos = set(), []
    for page in range(1, max(1, args.pages) + 1):
        rows = parse_response(fetch_page(session, keyword, page))
        added = 0
        for v in rows:
            if v["id"] in seen:
                continue
            seen.add(v["id"])
            videos.append(v)
            added += 1
        print(f"  第{page}页 {len(rows)} 条，新增 {added}，累计 {len(videos)}", flush=True)
        if added == 0:
            print("  提示：站点分页需要浏览器会话，本关键词仅能拿到首页结果", flush=True)
            break
        if args.limit and len(videos) >= args.limit:
            videos = videos[: args.limit]
            break
        if page < args.pages:
            time.sleep(args.delay)

    result = {
        "source": "acfun",
        "query": keyword,
        "pages": args.pages,
        "count": len(videos),
        "videos": videos,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"A站搜索「{keyword}」共 {len(videos)} 条，已写入 {out}")
    for v in videos[:10]:
        print(f"  {v['id']} {v['title'][:38]} | {v['author'][:14]} | {v['duration']}s | {v['view_count']}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "title", "author", "duration", "view_count",
                        "pubdate", "url"])
            for v in videos:
                w.writerow([v["id"], v["title"], v["author"], v["duration"],
                            v["view_count"], v["pubdate"], v["url"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
