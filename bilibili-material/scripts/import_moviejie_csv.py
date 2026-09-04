#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电影街油猴脚本「导出CSV」文件导入器。

当电影街反爬导致脚本直连不可用时，可在浏览器登录态下点油猴脚本的
「📥 导出CSV」，把下载的 CSV 文件导入本工具，合并去重后输出与采集器
同构的 JSON/CSV，方便直接入库。

Usage:
  python import_moviejie_csv.py --csv 电影街_2026-08-16.csv \
      --out moviejie_export.json --csv-out moviejie_export.csv
  python import_moviejie_csv.py --csv a.csv --csv b.csv --out moviejie.json
"""
import argparse
import csv
import json
import os
import sys

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s



def load_rows(paths):
    seen, rows = set(), []
    for fp in paths:
        with open(fp, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("资源名称") or "").strip()
                if not name:
                    continue
                rec = {
                    "name": name,
                    "category": (row.get("类型") or "").strip() or "电影",
                    "size": (row.get("大小") or "-").strip(),
                    "seeders": (row.get("做种数") or "0").strip(),
                    "leechers": (row.get("下载数") or "0").strip(),
                    "link": (row.get("下载链接") or "无链接").strip(),
                }
                key = name + "|" + rec["link"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(rec)
    rows.sort(key=lambda r: r["name"])
    return rows


def main():
    ap = argparse.ArgumentParser(description="电影街油猴导出 CSV 导入器")
    ap.add_argument("--csv", required=True, nargs="+",
                    help="油猴脚本导出的 CSV 文件（可多个）")
    ap.add_argument("--out", default="moviejie_export.json", help="输出 JSON")
    ap.add_argument("--csv-out", default=None, help="可选输出 CSV（默认同 --out 改名）")
    args = ap.parse_args()

    rows = load_rows(args.csv)
    movies = sum(1 for r in rows if r["category"] == "电影")
    tvs = len(rows) - movies
    result = {
        "source": "moviejie",
        "source_files": [os.path.basename(p) for p in args.csv],
        "imported_via": "userscript_csv",
        "count": len(rows),
        "movies": movies,
        "tvs": tvs,
        "resources": rows,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    csv_out = args.csv_out or os.path.splitext(out)[0] + ".csv"
    with open(csv_out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["类型", "资源名称", "大小", "做种数", "下载数", "下载链接"])
        for r in rows:
            w.writerow([r["category"], r["name"], r["size"], r["seeders"],
                        r["leechers"], r["link"]])
    print(f"导入完成：{len(rows)} 条（电影 {movies} / 剧集 {tvs}）")
    print(f"JSON: {out}")
    print(f"CSV:  {os.path.abspath(csv_out)}")


if __name__ == "__main__":
    main()
