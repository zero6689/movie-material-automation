# -*- coding: utf-8 -*-
"""2026-08-29 电影线索引增强：补 分类/分级/QA/清洗记录/高能点。"""
import csv
import datetime
import json
import os
import re
import sys

def csv_cell(v):
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

WORK = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WORK)
idx = json.load(open(os.path.join(ROOT, "index", "index.json"), encoding="utf-8"))
cand = {x["id"]: x for x in json.load(open(os.path.join(WORK, "candidates.json"), encoding="utf-8"))}

META = {
    "BV1Ci8S6dEaX": ("科幻/经典正片名场面", "《星河战队》影史名场面切片", "待定",
                     "右上平台水印带 y30-59（orig）已裁：crop_top60，PIL 顶带梯度 72-82% 下降，底部字幕带保留",
                     "音轨修复（video-only+f30280.m4a 合并，.videoonly.mp4 备份保留）+ crop_top60，setsar=1 回放 1280x720"),
    "BV1ra4f6zELb": ("经典/4K修复宣传", "《肖申克的救赎》4K修复版内地首映宣传物料（今日热点）", "待定",
                     "左上 UP 水印 y25-59（官方脚本漏检，四角复核定位）：crop_top60，PIL 顶带梯度 78-89% 下降，底部字幕带保留",
                     "音轨修复（video-only+f30280.m4a 合并）+ crop_top60，setsar=1 回放 1280x720"),
    "BV1St4k6ME6B": ("港片动作名场面", "《纵横四海》经典名场面切片", "待定",
                     "左上水印 y35-59：crop_top60，PIL 第3帧顶带梯度下降 83%；首尾帧顶部为画面内容，裁切后内容完整性 corr>0.75",
                     "音轨修复（video-only+f30280.m4a 合并）+ crop_top60，setsar=1 回放 720x720"),
    "ac18246132": ("港片喜剧经典4K修复", "《功夫》4K修复60帧名场面精华剪辑", "待定",
                   "右上水印带 y45-79（orig）已裁：crop_top80，PIL 顶带梯度 98-99% 下降，底部无字幕带",
                   "crop_top80，setsar=1 回放 1920x1080，原声保留"),
    "ac10075189": ("欧美DC预告", "《小丑》首曝官方预告（杰昆·菲尼克斯）", "待定",
                   "四角顶部干净（tr_ratio 1.94 实为底部字幕带 y1015-1079），不裁顶",
                   "原样入库 as-is，底部中文字幕保留，原声保留"),
    "ac3972416": ("华语科幻动作预告", "《机器之血》焕燃一新版预告片+概念版预告（1080P）", "待定",
                  "四角干净（PIL persist 无持久带），中部字幕为预告片字幕，按规则保留",
                  "原样入库 as-is，原声保留"),
}

NOTE = ("视觉复核：GLM-4V 429 余额耗尽（code 1113）不可用；按规则以 PIL 像素/梯度+跨帧持久性定量为准，"
        "最终裁切决定来自四角 row-profile 定量")


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
    print(f"  {e['id']:16s} {e['source']:8s} [{e['tier']}] {e['resolution']:10s} high={e['high_energy'][:36]}")
