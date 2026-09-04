# -*- coding: utf-8 -*-
"""Yandex 图片搜索采集（封面/素材图）。

用法：
  python collect_yandex_images.py --keyword "巫师3 重制版" --limit 10 --out-dir 封面/
  python collect_yandex_images.py --keyword-file kw.txt --limit 8 --out-dir 封面/
  python collect_yandex_images.py --keyword "巫师3" --limit 20 --out-dir 封面/ --min-width 1000

说明：
- 目标站点 yandex.ru/images（yandex.com 仅返回 JS 壳，不可用）。
- 结果内嵌在搜索页 JSON（"origin":{"w":N,"h":N,"url":...}），无需登录；
  脚本带会话 Cookie 访问，遇验证码会报错退出。
- 安全硬化（2026-09-04 security scan）：
  * 全程启用 TLS 证书校验（不再使用 verify=False）；
  * 只接受 https:// 图片目标；
  * 下载前校验 Content-Type 为 image/*，限制单文件大小（默认 30MB）。
- 图源为第三方站点原图（如 CDPR/媒体图床），商用/发布前请自行确认版权与平台规则。
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.parse

import requests

sys.stdout.reconfigure(encoding="utf-8")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MAX_IMAGE_BYTES = 30 * 1024 * 1024
IMG_RE = re.compile(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", re.I)
ORIGIN_RE = re.compile(r'"origin":\{"w":(\d+),"h":(\d+),"url":"([^"]+)"')
IMGURL_RE = re.compile(r'"img_url":"([^"]+)"')


def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9,ru;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    s.get("https://yandex.ru/", timeout=30)  # 拿 yandexuid 等 Cookie
    return s


def is_safe_image_url(u):
    """只放行 https 图片 URL（防降级 http 与任意协议）。"""
    if not u.startswith("https://"):
        return False
    if not IMG_RE.search(u):
        return False
    try:
        return urllib.parse.urlparse(u).scheme == "https"
    except Exception:
        return False


def search(sess, kw, page=0, large=True, min_width=0):
    params = {"text": kw, "p": page, "noreask": 1}
    if large:
        params["isize"] = "large"
    url = "https://yandex.ru/images/search?" + urllib.parse.urlencode(params)
    r = sess.get(url, timeout=40)
    r.raise_for_status()
    t = html.unescape(r.text)
    if "SmartCaptcha" in t or "captcha" in t.lower()[:20000]:
        raise RuntimeError("Yandex 返回验证码页，请稍后重试或换网络")
    items = []
    seen = set()
    for m in ORIGIN_RE.finditer(t):
        w, h = int(m.group(1)), int(m.group(2))
        u = m.group(3).replace("\\/", "/").replace("\\u0026", "&")
        if w < min_width or not is_safe_image_url(u):
            continue
        if u not in seen:
            seen.add(u)
            items.append({"url": u, "w": w, "h": h})
    if not items:  # 旧版结构兜底
        for u in IMGURL_RE.findall(t):
            u = u.replace("\\/", "/").replace("\\u0026", "&")
            if is_safe_image_url(u) and u not in seen:
                seen.add(u)
                items.append({"url": u, "w": 0, "h": 0})
    return url, items


def download_image(sess, url, dest, max_bytes=MAX_IMAGE_BYTES):
    """带 Content-Type 与大小限制的图片下载（流式，防任意文件/超大文件落盘）。"""
    with sess.get(url, headers={"Referer": "https://yandex.ru/"},
                  timeout=40, stream=True) as r:
        r.raise_for_status()
        ctype = (r.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("image/"):
            raise RuntimeError(f"非图片 Content-Type: {ctype or '未知'}")
        length = r.headers.get("Content-Length")
        if length:
            try:
                if int(length) > max_bytes:
                    raise RuntimeError(f"超过大小上限: {length} bytes")
            except ValueError:
                pass
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    os.remove(dest)
                    raise RuntimeError(f"下载超过大小上限: {total} bytes")
                f.write(chunk)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="")
    ap.add_argument("--keyword-file", default="")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out-dir", default="封面")
    ap.add_argument("--min-width", type=int, default=0)
    ap.add_argument("--page", type=int, default=0)
    args = ap.parse_args()

    kws = []
    if args.keyword:
        kws.append(args.keyword)
    if args.keyword_file:
        with open(args.keyword_file, encoding="utf-8-sig") as f:
            kws += [ln.strip() for ln in f if ln.strip()]

    os.makedirs(args.out_dir, exist_ok=True)
    sess = get_session()
    manifest = []
    for kw in kws:
        try:
            page_url, items = search(sess, kw, page=args.page,
                                     min_width=args.min_width)
        except Exception as e:
            print(f"[{kw}] 搜索失败: {e}", file=sys.stderr)
            continue
        got = 0
        for i, it in enumerate(items[: args.limit]):
            u = it["url"]
            ext = os.path.splitext(urllib.parse.urlparse(u).path)[1].lower() or ".jpg"
            name = f"{re.sub(r'[\\/:*?\"<>|\s]+', '_', kw)}_{i:02d}{ext}"
            dest = os.path.join(args.out_dir, name)
            if os.path.exists(dest):
                got += 1
                manifest.append({"keyword": kw, "url": u, "file": dest,
                                 "w": it["w"], "h": it["h"], "exists": True})
                continue
            try:
                size = download_image(sess, u, dest)
                got += 1
                manifest.append({"keyword": kw, "url": u, "file": dest,
                                 "w": it["w"], "h": it["h"],
                                 "size": size, "exists": False})
                print(f"[{kw}] {got}/{len(items[:args.limit])} {dest} "
                      f"({it['w']}x{it['h']}, {size}B)")
            except Exception as e:
                if os.path.exists(dest):
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                print(f"[{kw}] 下载失败 {u[:90]}: {e}", file=sys.stderr)
        print(f"[{kw}] 完成，下载 {got} 张，来源页 {page_url}")

    with open(os.path.join(args.out_dir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"manifest: {os.path.join(args.out_dir, 'manifest.json')} 共 {len(manifest)} 条")


if __name__ == "__main__":
    main()
