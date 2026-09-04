# -*- coding: utf-8 -*-
"""按人工精选 ID 覆盖 selection.json / urls / summary（B站 3 + A站 3）。"""
import csv, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
WORK = os.path.dirname(os.path.abspath(__file__))

BILI_IDS = ["BV1cAtN69E8H", "BV1Q3th6VEXA", "BV1be426SEth"]
ACFUN_IDS = ["ac18859904", "ac16068011", "ac31495298"]
NOTES = {
    "BV1cAtN69E8H": "人工精选：71万播放科幻名场面原声候选；曾 412 风控，失败则走 download_api 兜底",
    "BV1Q3th6VEXA": "人工精选：今日发布 13k 播放 90s 电影向短片，原声候选待验证内容",
    "BV1be426SEth": "人工精选：自杀小队断臂侠名场面 20k 播放，DC 动作向",
    "ac18859904": "脚本精选：电影四大加钱名场面 44k 播放，名场面素材",
    "ac16068011": "脚本精选：张艺谋《坚如磐石》首曝预告，官方预告向",
    "ac31495298": "脚本精选：发哥《别叫我赌神》先导预告，官方预告向",
}

cands = json.load(open(os.path.join(WORK, "candidates.json"), encoding="utf-8"))
by_id = {it["id"]: it for it in cands}

sel = []
for pid in BILI_IDS + ACFUN_IDS:
    it = dict(by_id[pid])
    it["manual_note"] = NOTES.get(pid, "")
    sel.append(it)

with open(os.path.join(WORK, "selection.json"), "w", encoding="utf-8") as f:
    json.dump(sel, f, ensure_ascii=False, indent=2)

with open(os.path.join(WORK, "urls_bili.txt"), "w", encoding="utf-8") as f:
    for it in sel:
        if it["source"] == "bilibili":
            f.write(it["url"] + "\n")

with open(os.path.join(WORK, "urls_acfun.txt"), "w", encoding="utf-8") as f:
    for it in sel:
        if it["source"] == "acfun":
            f.write(it["url"] + "\n")

lines = ["# 2026-08-31 精选（人工校正）", "B站 top3:"]
for it in sel:
    if it["source"] == "bilibili":
        lines.append(f"  {it['id']} [{it['tier']}] 播放{it['play']} {it['title'][:70]}")
        lines.append(f"    注: {it['manual_note']}")
lines.append("A站 top3:")
for it in sel:
    if it["source"] == "acfun":
        lines.append(f"  {it['id']} [{it['tier']}] 播放{it['play']} {it['title'][:70]}")
        lines.append(f"    注: {it['manual_note']}")
open(os.path.join(WORK, "selection_summary.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
