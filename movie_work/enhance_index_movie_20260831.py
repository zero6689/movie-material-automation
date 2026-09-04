# -*- coding: utf-8 -*-
"""2026-08-31 电影线索引增强：补 分类/分级/QA/清洗记录/高能点。"""
import csv
import datetime
import json
import os
import sys

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

WORK = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WORK)
idx = json.load(open(os.path.join(ROOT, "index", "index.json"), encoding="utf-8"))
cand = {x["id"]: x for x in json.load(open(os.path.join(WORK, "candidates.json"), encoding="utf-8"))}

META = {
    "BV1cAtN69E8H": ("科幻/国产大片名场面", "疑似《流浪地球2》名场面切片（弹幕台词佐证：门框机器人/没有人的文明毫无意义/100年转瞬之间，81条弹幕）", "原声候选",
                     "四角干净（PIL 四角 profile 无固定角标），底部字幕带 y600-649 保留不裁",
                     "音轨修复：video-only + f30280.m4a 合并，.videoonly.mp4 备份保留；原样入库 as-is"),
    "BV1Q3th6VEXA": ("电影向创意短片", "《它们如果出现在同一部电影里会怎样？》创意向短片（右中文字面板为内容保留）", "待定",
                     "右上固定水印 y25-65（PIL 3帧稳定）已裁：crop_top70，清洗后四角无固定角标",
                     "音轨修复（video-only+f30280.m4a 合并）+ crop_top70，setsar=1 回放 1280x720"),
    "BV1be426SEth": ("欧美DC/动作名场面", "《自杀小队》断臂侠超能力名场面切片", "待定",
                     "左上+右上双重水印 y25-90（PIL 3帧稳定）已裁：crop_top96，清洗后四角无固定角标；底部字幕带保留",
                     "音轨修复（video-only+f30280.m4a 合并）+ crop_top96，setsar=1 回放 1280x720"),
    "ac18859904": ("名场面合集/盘点向", "电影四大加钱名场面合集（44k播放，含多片名场面）", "二创待定",
                   "右上固定水印 y30-59（3帧稳定）已裁：crop_top64，清洗后四角无固定角标；中下部内容字幕保留",
                   "crop_top64，setsar=1 回放 1280x720，原声保留"),
    "ac16068011": ("华语犯罪片预告", "张艺谋《坚如磐石》首曝预告（乌鸦预告片，2020年旧预告非新片）", "待定",
                   "四角干净，底部字幕带 y700-719 保留不裁；中部标题卡为预告内容",
                   "原样入库 as-is，原声保留"),
    "ac31495298": ("港片预告", "发哥《别叫我“赌神”》首曝先导预告（2021年旧预告非新片）", "待定",
                   "左上固定叠加 y10-124（跨帧静止验证 35k+ 像素复现，官方脚本漏检）已裁：crop_top128，清洗后四角无固定角标",
                   "crop_top128，setsar=1 回放 1920x1080，原声保留"),
}

NOTE = ("视觉复核：DeepSeek-V4-Flash-Vision-Exp 子代理 + PIL 四角 row-profile/跨帧静止定量；视觉模型多次误报/跑偏，"
        "最终以 PIL 像素定量为准")


def high_energy(vid):
    js = os.path.join(WORK, f"danmaku_{vid}.json")
    if not os.path.exists(js):
        return "无（未抓取弹幕）"
    data = json.load(open(js, encoding="utf-8"))
    hs = data.get("hotspots", [])
    if not hs:
        return f"无（弹幕 {data.get('count', 0)} 条，无高能点）"
    top = sorted(hs, key=lambda x: -x["danmaku"])[:8]
    top.sort(key=lambda x: x["time"])
    return "、".join(f"{int(h['time'])}s({h['danmaku']}条)" for h in top)


for e in idx["entries"]:
    name = os.path.splitext(os.path.basename(e["file"]))[0]
    c = cand.get(name, {})
    cat, subj, tier, qa, clean = META.get(name, ("", "", c.get("tier", ""), "", ""))
    e["id"] = name
    e["subject"] = subj
    e["category"] = cat
    e["source"] = c.get("source", "")
    e["line"] = "movie"
    e["title"] = c.get("title", "")
    e["uploader"] = c.get("author", "")
    e["play"] = c.get("play", 0)
    e["danmaku"] = c.get("danmaku", 0)
    e["tier"] = tier or c.get("tier", "")
    e["url"] = c.get("url", "")
    pub = c.get("pubdate", 0)
    e["pubdate"] = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d") if pub else ""
    e["qa"] = qa
    e["cleaning"] = clean
    e["qa_note"] = NOTE
    e["high_energy"] = high_energy(name) if e["source"] == "bilibili" else "A站无弹幕接口"

with open(os.path.join(ROOT, "index", "index.json"), "w", encoding="utf-8") as f:
    json.dump(idx, f, ensure_ascii=False, indent=2)

cols = ["file", "id", "source", "line", "category", "subject", "title", "uploader",
        "duration", "resolution", "size_mb", "play", "danmaku", "pubdate",
        "tier", "url", "qa", "cleaning", "qa_note", "high_energy", "tag"]
with open(os.path.join(ROOT, "index", "index.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for e in idx["entries"]:
        w.writerow([csv_cell(e.get(k, "")) if k in {"category","subject","title","uploader","qa","cleaning","qa_note","high_energy","url"} else e.get(k, "") for k in cols])

print(f"enhanced {len(idx['entries'])} entries")
for e in idx["entries"]:
    print(f"  {e['id']:16s} {e['source']:8s} [{e['tier']}] {e['resolution']:10s} high={e['high_energy'][:40]}")
