#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电影街（moviejie.net）资源采集器。

站点是登录墙：资源列表 /new/、搜索 /search/q_<关键词>/、磁力搜索结果都要求
登录态，匿名访问会被 302 到 /user/login/。因此本脚本必须带 moviejie.net 的
登录 Cookie（Netscape cookies.txt 或 cookie 字符串），并内置低频访问与失败
退避，避免触发站点风控（本站对高频探测会临时封 IP）。

Usage:
  python search_moviejie.py --mode latest --cookies cookies.txt --pages 2 \
      --out moviejie.json --csv moviejie.csv
  python search_moviejie.py --mode search --keyword "沙丘2" --cookies cookies.txt \
      --out moviejie.json
  python search_moviejie.py --url "https://moviejie.net/new/" \
      --cookie-string "k=v; k2=v2" --out moviejie.json
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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://moviejie.net"

TAG_RE = re.compile(r"<[^>]+>")
ROWS_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RESTITLE_RE = re.compile(r'class="[^"]*\brestitle\b[^"]*"[^>]*>(.*?)</',
                         re.I | re.S)
TDS_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.I | re.S)
SEEDER_RE = re.compile(r'class="[^"]*\bseeders\b[^"]*"[^>]*>(.*?)</',
                       re.I | re.S)
LEECH_RE = re.compile(r'class="[^"]*\bleechers\b[^"]*"[^>]*>(.*?)</',
                      re.I | re.S)
LINK_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']*(?:/download/|magnet:|thunder:)[^"\']*)["\']',
    re.I)
NEXT_RE = re.compile(
    r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>\s*"
    r"(?:下一页|下页|»|&raquo;|&gt;&gt;|next)\s*</a>",
    re.I | re.S)


def classify_resource(name):
    """按名称粗分 电影 / 剧集（与油猴脚本同一套关键词）。"""
    lower = name.lower()
    tv_keywords = [
        "s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09",
        "s10", "season", "ep", "e01", "e02", "e03", "e04", "e05", "e06",
        "e07", "e08", "e09", "第", "集", "季", "全", "完", "hdtv",
        "webrip", "s01e", "s02e",
    ]
    if any(kw in lower for kw in tv_keywords):
        return "剧集"
    if "第" in lower and "集" in lower:
        return "剧集"
    if re.search(r"\d{2,}集", name):
        return "剧集"
    return "电影"


def clean(s):
    s = TAG_RE.sub("", s or "")
    s = s.replace("↗", "").replace("&nbsp;", " ").strip()
    return s


def load_cookies(path):
    """解析 Netscape cookies.txt（按 UTF-8 读取，兼容 GBK 终端环境）。"""
    from http.cookiejar import Cookie, MozillaCookieJar

    jar = MozillaCookieJar()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, include_sub, cpath, secure, expires, name, value = parts[:7]
            try:
                exp = None if expires == "0" else int(expires)
            except ValueError:
                exp = None
            c = Cookie(
                version=0, name=name, value=value, port=None,
                port_specified=False,
                domain=domain, domain_specified=include_sub == "TRUE",
                domain_initial_dot=domain.startswith("."),
                path=cpath, path_specified=True, secure=secure == "TRUE",
                expires=exp, discard=True, comment=None,
                comment_url=None, rest={}, rfc2109=False,
            )
            jar.set_cookie(c)
    return jar


def cookie_string_to_dict(s):
    d = {}
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def make_session(cookies_path=None, cookie_string=None):
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": BASE + "/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if cookie_string:
        s.cookies.update(cookie_string_to_dict(cookie_string))
    elif cookies_path:
        s.cookies = load_cookies(cookies_path)
    return s


def fetch(session, url, timeout=20, retries=3, delay=3.0):
    last = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if "/user/login/" in r.url:
                raise SystemExit(
                    f"需要登录态：{url} 被重定向到登录页。请先登录 moviejie.net "
                    "并导出 Netscape 格式 Cookie（见 SKILL.md / workflow.md 说明）。")
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
            wait = delay * (2 ** i)
            print(f"  请求失败（{type(e).__name__}），{wait:.0f}s 后重试: {url}",
                  flush=True)
            time.sleep(wait)
    raise SystemExit(f"连续 {retries} 次请求失败: {last}")


def parse_rows(html):
    rows = []
    for m in ROWS_RE.finditer(html):
        tr = m.group(1)
        nm = RESTITLE_RE.search(tr)
        if not nm:
            continue
        name = clean(nm.group(1))
        if not name:
            continue

        tds = TDS_RE.findall(tr)
        size = clean(tds[1]) if len(tds) > 1 else "-"
        seed_m = SEEDER_RE.search(tr)
        leech_m = LEECH_RE.search(tr)
        seeders = clean(seed_m.group(1)) if seed_m else "0"
        leechers = clean(leech_m.group(1)) if leech_m else "0"

        link_m = LINK_RE.search(tr)
        if link_m:
            link = link_m.group(1)
        else:
            link = "VIP可见" if "VIP" in tr else "无链接"

        rows.append({
            "name": name,
            "category": classify_resource(name),
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
            "link": link,
        })
    return rows


def next_url(html, current):
    m = NEXT_RE.search(html)
    if not m:
        return None
    nxt = urllib.parse.urljoin(current, m.group(1))
    if nxt == current or nxt.rstrip("/") == current.rstrip("/"):
        return None
    return nxt


def build_start_url(args):
    if args.url:
        return args.url
    if args.mode == "search":
        if not args.keyword:
            raise SystemExit("--mode search 需要 --keyword")
        return f"{BASE}/search/q_{urllib.parse.quote(args.keyword)}/"
    return f"{BASE}/new/"


def main():
    ap = argparse.ArgumentParser(description="电影街（moviejie.net）资源采集")
    ap.add_argument("--mode", choices=["latest", "search"], default="latest",
                    help="latest=最新资源列表（默认）；search=关键词搜索")
    ap.add_argument("--keyword", default=None, help="搜索关键词（--mode search 时用）")
    ap.add_argument("--url", default=None, help="直接指定列表页 URL（覆盖 mode）")
    ap.add_argument("--cookies", default=None, help="Netscape 格式 cookies.txt（必填之一）")
    ap.add_argument("--cookie-string", default=None,
                    help='直接传 cookie 字符串，如 "k=v; k2=v2"（与 --cookies 二选一）')
    ap.add_argument("--pages", type=int, default=1, help="最多翻页数（默认 1）")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="每次请求间隔秒数（默认 3，别改小，站点反爬敏感）")
    ap.add_argument("--timeout", type=int, default=20, help="单请求超时秒数")
    ap.add_argument("--limit", type=int, default=0, help="最多保留条数（0=不限）")
    ap.add_argument("--out", default="moviejie.json", help="输出 JSON")
    ap.add_argument("--csv", default=None, help="可选 CSV 输出")
    args = ap.parse_args()

    if not args.cookies and not args.cookie_string:
        raise SystemExit(
            "缺少登录态：请提供 --cookies cookies.txt 或 --cookie-string。"
            "moviejie.net 匿名访问会被重定向到登录页。")

    session = make_session(args.cookies, args.cookie_string)
    start = build_start_url(args)
    page_limit = max(1, args.pages)

    seen, resources = set(), []
    url, pages = start, 0
    while url and pages < page_limit:
        pages += 1
        print(f"[{pages}/{page_limit}] {url}", flush=True)
        html = fetch(session, url, timeout=args.timeout, delay=args.delay)
        rows = parse_rows(html)
        added = 0
        for row in rows:
            key = row["name"] + "|" + row["link"]
            if key in seen:
                continue
            seen.add(key)
            row["url"] = url
            resources.append(row)
            added += 1
        print(f"  本页 {len(rows)} 行，新增 {added} 条，累计 {len(resources)}",
              flush=True)
        if args.limit and len(resources) >= args.limit:
            resources = resources[: args.limit]
            break
        nxt = next_url(html, url)
        if not nxt:
            break
        url = nxt
        time.sleep(args.delay)

    movies = sum(1 for r in resources if r["category"] == "电影")
    tvs = len(resources) - movies
    result = {
        "source": "moviejie",
        "query": args.keyword or "latest",
        "pages": pages,
        "count": len(resources),
        "movies": movies,
        "tvs": tvs,
        "resources": resources,
    }
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"电影街采集完成：共 {len(resources)} 条（电影 {movies} / 剧集 {tvs}），"
          f"已写入 {out}")
    for r in resources[:10]:
        print(f"  【{r['category']}】{r['name'][:40]} | {r['size']} | "
              f"做种 {r['seeders']} | 下载 {r['leechers']} | {r['link'][:60]}")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["类型", "资源名称", "大小", "做种数", "下载数", "下载链接"])
            for r in resources:
                w.writerow([r["category"], r["name"], r["size"],
                            r["seeders"], r["leechers"], r["link"]])
        print(f"CSV 已写入: {os.path.abspath(args.csv)}")


if __name__ == "__main__":
    main()
