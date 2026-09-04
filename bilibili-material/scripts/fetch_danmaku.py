#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch danmaku for a Bilibili video and locate high-energy moments.

Accepts a bvid (resolves cid via the view API) or a raw cid. Outputs the
danmaku list as JSON/CSV plus hotspot windows by danmaku density.

Usage:
  python fetch_danmaku.py --bvid BV1px411o7jN --out danmaku.json
  python fetch_danmaku.py --cid 98999350 --window 5 --top 20 --csv danmaku.csv
"""
import argparse
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DM_URL = "https://api.bilibili.com/x/v1/dm/list.so"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    return s


def resolve_cid(s, bvid):
    r = s.get(VIEW_URL, params={"bvid": bvid}, timeout=20)
    d = r.json()
    if d.get("code") != 0:
        raise SystemExit(f"解析 cid 失败 code={d.get('code')} msg={d.get('message')}")
    data = d["data"]
    return data["cid"], data.get("title", ""), data.get("owner", {}).get("name", "")


def fetch(s, cid):
    r = s.get(DM_URL, params={"oid": cid}, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for d in root.findall(".//d"):
        p = (d.get("p") or "").split(",")
        try:
            t_ms = float(p[0])
        except (IndexError, ValueError):
            continue
        color = p[3] if len(p) > 3 else "16777215"
        out.append({"time": round(t_ms, 3), "color": color,
                    "text": (d.text or "").strip()})
    return out


def hotspots(items, window=5, top=20):
    times = sorted(x["time"] for x in items)
    if not times:
        return []
    end = times[-1]
    out = []
    t = 0.0
    while t < end:
        cnt = sum(1 for x in times if t <= x < t + window)
        out.append((round(t + window / 2, 1), cnt))
        t += 1.0
    out.sort(key=lambda x: x[1], reverse=True)
    picked = []
    for center, cnt in out:
        if any(abs(center - p["time"]) < window for p in picked):
            continue
        picked.append({"time": center, "window": window, "danmaku": cnt})
        if len(picked) >= top:
            break
    return sorted(picked, key=lambda x: x["time"])


def main():
    ap = argparse.ArgumentParser(description="B 站弹幕采集与高能时刻")
    ap.add_argument("--bvid", default=None, help="视频 BV 号")
    ap.add_argument("--cid", type=int, default=None, help="视频 cid（与 --bvid 二选一）")
    ap.add_argument("--out", default="danmaku.json", help="输出 JSON")
    ap.add_argument("--csv", default=None, help="可选：弹幕 CSV")
    ap.add_argument("--window", type=float, default=5.0, help="高能统计窗口（秒，默认 5）")
    ap.add_argument("--top", type=int, default=20, help="高能时刻数量（默认 20）")
    args = ap.parse_args()

    s = session()
    title, author = "", ""
    if args.bvid:
        cid, title, author = resolve_cid(s, args.bvid)
    elif args.cid:
        cid = args.cid
    else:
        raise SystemExit("请提供 --bvid 或 --cid")

    items = fetch(s, cid)
    result = {
        "bvid": args.bvid,
        "cid": cid,
        "title": title,
        "author": author,
        "count": len(items),
        "hotspots": hotspots(items, args.window, args.top),
        "danmaku": items,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"{title or args.bvid or cid} 弹幕 {len(items)} 条")
    print(f"前 8 个高能时刻（{args.window}s 窗口）:")
    for h in result["hotspots"][:8]:
        print(f"  {h['time']:.1f}s  {h['danmaku']} 条")
    print(f"已写入: {out}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "color", "text"])
            for x in items:
                w.writerow([x["time"], x["color"], csv_cell(x["text"])])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
