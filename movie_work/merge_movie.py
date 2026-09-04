# -*- coding: utf-8 -*-
"""电影线：合并 B站 + A站搜索结果，电影类过滤、分级、历史去重、每平台 top3 精选。"""
import csv, glob, json, os, re, sys, time
from datetime import datetime

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

WORK = os.path.dirname(os.path.abspath(__file__))
NOW = time.time()
WINDOW = 7 * 86400

MOVIE = re.compile(r"电影|片名|预告|名场面|经典|修复|4K|60帧|欧美|好莱坞|漫威|DC|奥斯卡|"
                   r"海外片|新片|大片|首映|定档|上映|正片|科幻|动作|武侠|恐怖|悬疑|惊悚|"
                   r"喜剧|剧场版|动画电影|影评|影视|影片")
NEG = re.compile(r"真人秀|综艺|剧集|新剧|电视剧|动漫剧|游戏|玩家|主播|直播间|短片集|"
                 r"特辑|幕后花絮|彩蛋解析")
TV = re.compile(r"甄嬛|如懿|人世间|第\d+集|华妃|熹妃|皇后|梦华录|唐宁街|汉弗莱|熊出没|"
                 r"老詹|NBA|篮球|整蛊|搞怪|狼人杀")
FAN = re.compile(r"解说|盘点|评测|测评|指南|选购|推荐|速递|吐槽|回顾|梳理|翻拍|自制|原创|"
                 r"AI|漫剧|短剧|混剪|AMV|BGM|配音|段子|搞笑|爆笑|抽象|攻略|实况|直播|试玩|"
                 r"教学|讲述|串讲|全结局|全通关|一口气看完|建议收藏|影评|点评|排名|榜单")
FAN = re.compile(r"解说|解析|盘点|评测|测评|指南|选购|推荐|速递|吐槽|回顾|梳理|翻拍|自制|原创|"
                 r"AI|漫剧|短剧|混剪|AMV|BGM|配音|段子|搞笑|爆笑|抽象|攻略|实况|直播|试玩|"
                 r"教学|讲述|串讲|全结局|全通关|一口气看完|建议收藏|影评|点评|排名|榜单")
MAYBE = re.compile(r"片段|名场面|预告|纯享|精选|4K|无水印|60帧|高能|修复|1080P|1080p")


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    if isinstance(d, dict) and isinstance(d.get("videos"), list):
        return d["videos"]
    if isinstance(d, list):
        return d
    return []


def parse_date(v):
    if isinstance(v, (int, float)) and v > 0:
        return int(v)
    if isinstance(v, str):
        try:
            return int(datetime.strptime(v[:10], "%Y-%m-%d").timestamp())
        except Exception:
            return 0
    return 0


def norm(item, src, cat):
    vid = item.get("bvid") or item.get("acId") or item.get("id") or item.get("acid") or ""
    title = item.get("title") or item.get("name") or ""
    dur = item.get("duration") or 0
    try:
        dur = int(float(dur))
    except Exception:
        dur = 0
    play = item.get("play") or item.get("view") or item.get("view_count") or 0
    try:
        play = int(float(play))
    except Exception:
        play = 0
    dm = item.get("danmaku") or item.get("video_review") or 0
    try:
        dm = int(float(dm))
    except Exception:
        dm = 0
    pub = parse_date(item.get("pubdate"))
    return {
        "id": str(vid), "source": src, "category": cat,
        "title": str(title).strip(),
        "author": str(item.get("author") or item.get("upName") or "").strip(),
        "duration": dur, "play": play, "danmaku": dm, "pubdate": pub,
        "pubdate_str": datetime.fromtimestamp(pub).strftime("%Y-%m-%d %H:%M") if pub else "",
        "url": item.get("url") or f"https://www.acfun.cn/v/{vid}",
    }


def tier(title):
    if FAN.search(title):
        return "二创"
    if MAYBE.search(title):
        return "待定"
    return "原声候选"


def _library_root():
    """素材库根：优先 MATERIAL_ROOT 环境变量，其次工作目录下的 素材库/。"""
    p = os.environ.get("MATERIAL_ROOT", "").strip().strip('\"')
    if p and os.path.isdir(p):
        return p
    local = os.path.join(os.getcwd(), "素材库")
    return local if os.path.isdir(local) else ""


def history_ids():
    """扫描素材库历史，收集已有 bvid/acId 与 (标题,时长) 指纹。"""
    ids, fingerprints = set(), set()
    root = _library_root()
    if not root:
        return ids, fingerprints  # 未配置素材库根目录时跳过历史去重
    patterns = [
        # 只把“实际下载/入库”的素材视为历史；candidates.json 只是侦察结果，不算已采集
        os.path.join(root, "**", "download_manifest.json"),
        os.path.join(root, "**", "index.json"),
    ]
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            try:
                d = json.load(open(p, encoding="utf-8-sig"))
            except Exception:
                continue
            items = d if isinstance(d, list) else d.get("items") or d.get("materials") or d.get("videos") or []
            for it in items:
                if not isinstance(it, dict):
                    continue
                iid = it.get("id") or it.get("bvid") or it.get("acId") or ""
                if iid:
                    ids.add(str(iid))
                title = it.get("title") or ""
                dur = it.get("duration") or 0
                if title and dur:
                    fingerprints.add(f"{title}|{dur}")
    # 也扫实际下载文件
    for p in glob.glob(os.path.join(root, "**", "bilibili", "BV*.mp4"), recursive=True):
        m = re.search(r"(BV[0-9A-Za-z]+)", os.path.basename(p))
        if m:
            ids.add(m.group(1))
    for p in glob.glob(os.path.join(root, "**", "acfun", "ac*.mp4"), recursive=True):
        m = re.search(r"(ac\d+)", os.path.basename(p))
        if m:
            ids.add(m.group(1))
    return ids, fingerprints


def main():
    items = []
    for p in sorted(glob.glob(os.path.join(WORK, "bili_movie_*.json"))):
        cat = re.search(r"bili_movie_(\d+)", os.path.basename(p)).group(1)
        for it in load(p):
            items.append(norm(it, "bilibili", f"kw{cat}"))
    for p in sorted(glob.glob(os.path.join(WORK, "acfun_*.json"))):
        cat = re.search(r"acfun_(\d+)", os.path.basename(p)).group(1)
        for it in load(p):
            items.append(norm(it, "acfun", f"kw{cat}"))

    hist_ids, hist_fp = history_ids()

    seen, kept = {}, []
    for it in items:
        key = it["id"]
        if not key or key in seen:
            continue
        if not MOVIE.search(it["title"]) or NEG.search(it["title"]):
            continue
        # 电视剧/动画剧集名场面误入：除非标题明确是大电影/剧场版
        if TV.search(it["title"]) and not re.search(r"大电影|剧场版|电影", it["title"]):
            continue
        it["tier"] = tier(it["title"])
        it["recent"] = bool(it["pubdate"] and NOW - it["pubdate"] <= WINDOW)
        it["in_history"] = key in hist_ids or f"{it['title']}|{it['duration']}" in hist_fp
        if it["source"] == "bilibili" and not it["recent"]:
            continue  # B站只保留最近 7 天
        seen[key] = it
        kept.append(it)

    # 排序：原声 < 待定 < 二创；同层按 播放 > 弹幕 > 时长合适度
    def score(it):
        tr = {"原声候选": 0, "待定": 1, "二创": 2}[it["tier"]]
        bonus = 0
        if re.search(r"4K|1080P|1080p", it["title"]):
            bonus += 0.05
        if re.search(r"预告", it["title"]):
            bonus += 0.02
        return (tr, -it["play"], -it["danmaku"], -bonus)

    kept.sort(key=score)

    def pick(platform, cap=3):
        chosen, fan_count = [], 0
        for it in kept:
            if it["source"] != platform or it["in_history"]:
                continue
            if it["tier"] == "二创" and fan_count >= 3:
                continue
            if len(chosen) >= cap:
                break
            chosen.append(it)
            if it["tier"] == "二创":
                fan_count += 1
        return chosen

    sel_bili = pick("bilibili")
    sel_acfun = pick("acfun")
    selected = sel_bili + sel_acfun

    with open(os.path.join(WORK, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    with open(os.path.join(WORK, "candidates.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "tier", "title", "author", "duration", "play", "danmaku",
                    "pubdate", "recent", "in_history", "url"])
        for it in kept:
            w.writerow([it["id"], it["source"], it["tier"], it["title"], it["author"],
                        it["duration"], it["play"], it["danmaku"], it["pubdate_str"],
                        it["recent"], it["in_history"], it["url"]])
    with open(os.path.join(WORK, "selection.json"), "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)
    with open(os.path.join(WORK, "urls_bili.txt"), "w", encoding="utf-8") as f:
        for it in sel_bili:
            f.write(it["url"] + "\n")
    with open(os.path.join(WORK, "urls_acfun.txt"), "w", encoding="utf-8") as f:
        for it in sel_acfun:
            f.write(it["url"] + "\n")

    lines = [f"合并后电影候选: {len(kept)} 条"]
    for it in kept:
        flag = "★" if it in selected else " "
        tag = "历史重复" if it["in_history"] else it["tier"]
        lines.append(f"{flag} [{it['source']}] {it['id']} {tag} 播放{it['play']} {it['pubdate_str']} {it['title'][:50]}")
    lines.append("")
    lines.append("B站精选:")
    for it in sel_bili:
        lines.append(f"  {it['id']} {it['tier']} {it['title'][:60]}")
    lines.append("A站精选:")
    for it in sel_acfun:
        lines.append(f"  {it['id']} {it['tier']} {it['title'][:60]}")
    open(os.path.join(WORK, "selection_summary.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
