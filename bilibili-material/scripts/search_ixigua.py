#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""西瓜视频（Ixigua）关键词搜索。

西瓜搜索接口有 ByteDance 风控（ttwid + secsdk 签名）。脚本先自动走 ttwid
匿名流程，若仍被 WAF 拦截（返回 HTML 壳而非 JSON），需要 --cookies 传入
浏览器里 ixigua.com 的 cookies.txt（用 Get cookies.txt LOCALLY 导出）。

Usage:
  python search_ixigua.py --keyword "巫师3" --out ixigua.json --csv ixigua.csv
  python search_ixigua.py --keyword "游戏" --cookies ixigua_cookies.txt --out ixigua.json
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.parse

import requests

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TTWID_DATA = ('{"region":"cn","aid":1768,"needFid":false,'
              '"service":"www.ixigua.com","migrate_info":{"ticket":"",'
              '"source":"node"},"cbUrlProtocol":"https","union":true}')


def get_ttwid(session):
    r = session.post("https://ttwid.bytedance.com/ttwid/union/register/",
                     data=TTWID_DATA, timeout=20)
    cb = r.json().get("redirect_url", "")
    if cb:
        session.get(cb, timeout=20)
    return session.cookies.get_dict().get("ttwid")


def load_cookies_file(path):
    jar = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 7 and not parts[0].startswith("#"):
                jar[parts[5]] = parts[6]
    return jar


def fetch_search(session, keyword, cookies_file=None):
    if cookies_file:
        session.cookies.update(load_cookies_file(cookies_file))
    else:
        get_ttwid(session)
    params = {"keyword": keyword, "pd": "video", "count": "20",
              "source": "channel_pc_web", "aid": "1768"}
    r = session.get("https://www.ixigua.com/api/search/content/",
                    params=params, headers={"Referer": "https://www.ixigua.com/"},
                    timeout=25)
    text = r.text
    if not text.lstrip().startswith("{"):
        raise SystemExit(
            "西瓜搜索被风控拦截（返回了页面壳而非 JSON）。"
            "请用 --cookies 传入 ixigua.com 的 cookies.txt"
            "（浏览器 Get cookies.txt LOCALLY 导出）。")
    return json.loads(text)


def parse_results(data):
    videos = []
    items = []
    d = data.get("data") or {}
    if isinstance(d, list):
        items = d
    elif isinstance(d, dict):
        for k in ("data", "result", "video_list", "videoList"):
            v = d.get(k)
            if isinstance(v, list):
                items = v
                break
    for it in items:
        if not isinstance(it, dict):
            continue
        vid = it.get("group_id") or it.get("item_id") or it.get("video_id")
        if not vid:
            continue
        author = (it.get("author") or {})
        if isinstance(author, dict):
            author_name = author.get("name") or author.get("nickname") or ""
        else:
            author_name = str(author)
        videos.append({
            "id": str(vid),
            "title": it.get("title") or it.get("raw_title") or "",
            "author": author_name,
            "duration": int((it.get("video_duration") or 0) / 1000),
            "view_count": int(it.get("play_count") or it.get("statistics", {}).get("play_count") or 0),
            "pubdate": str(it.get("publish_time") or it.get("create_time") or ""),
            "url": f"https://www.ixigua.com/{vid}",
        })
    return videos


def main():
    ap = argparse.ArgumentParser(description="西瓜视频关键词搜索（Cookie 兜底）")
    ap.add_argument("--keyword", default=None)
    ap.add_argument("--keyword-file", default=None)
    ap.add_argument("--cookies", default=None, help="ixigua.com 的 cookies.txt（风控时必填）")
    ap.add_argument("--out", default="ixigua_search.json")
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
    data = fetch_search(session, keyword, args.cookies)
    videos = parse_results(data)
    result = {"source": "ixigua", "query": keyword, "count": len(videos),
              "videos": videos}
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"西瓜搜索「{keyword}」共 {len(videos)} 条，已写入 {out}")
    for v in videos[:10]:
        print(f"  {v['id']} {v['title'][:38]} | {v['author'][:14]} | {v['duration']}s")

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
