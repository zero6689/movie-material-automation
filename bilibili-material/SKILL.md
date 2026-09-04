---
name: bilibili-material
description: >
  B 站素材采集：按关键词搜索视频（免登录），批量下载并规范化成可剪辑 MP4，
  抓取弹幕并定位高能时刻，最后把素材整理成可检索的索引（JSON/CSV）。
  用于「B站」「bilibili」「BV号」「下载视频」「采集素材」「关键词搜索」
  「批量下载」「弹幕」「高能时刻」「素材库」「素材采集」「m4s 转 mp4」
  「找素材」「收集参考素材」等任务。
---

# Bilibili Material

## Overview

像磁力采集器一样工作：输入关键词 → 拿到视频列表 → 按条件过滤 → 批量下载入库，
顺带抓弹幕标出高能时刻。下载产物可直接喂给 `$beat-cut-sync`（卡点）和
`$subtitle-review`（字幕）。

选题调研请用 [$tanzi](C:/Users/85950/.codex/skills/tanzi/SKILL.md)（跨平台情报采集），
素材采集用本技能；tanzi 的 `01_清单.md` 提炼关键词后可直接作为本技能搜索输入。

## 工作流

脚本在 `scripts/` 下，用项目 Python 运行：
`V:\CodexProjects\Python\pythoncore-3.14-64\python.exe`（或 `python`）。

### 1. 关键词搜索

```bash
python scripts/search_bilibili.py --keyword-file kw.txt --out videos.json --csv videos.csv
python scripts/search_bilibili.py --keyword "巫师3 战斗" --pages 2 --order totalrank \
  --min-duration 120 --max-duration 1800 --min-play 10000 --min-danmaku 100 --limit 50
```

中文关键词建议用 `--keyword-file`（UTF-8 文件），避免 shell 编码问题。
排序：`totalrank`(综合) / `click`(播放) / `pubdate`(最新) / `dm`(弹幕) / `score`(评分)。
免登录即可用（脚本内置匿名指纹 Cookie）。

### 1.5 电影街资源采集（登录态站点）

```bash
python scripts/search_moviejie.py --mode latest --cookies cookies.txt --pages 2 \
  --out moviejie.json --csv moviejie.csv
python scripts/search_moviejie.py --mode search --keyword "沙丘2" --cookies cookies.txt \
  --out moviejie.json
python scripts/search_moviejie.py --url "https://moviejie.net/new/" \
  --cookie-string "k=v; k2=v2" --out moviejie.json
```

moviejie.net（电影街）是登录墙站点：最新/搜索/磁力结果页都要求登录，匿名访问
会被 302 到 `/user/login/`。脚本必须带 moviejie.net 的登录 Cookie（Netscape
格式 `cookies.txt`，或 `--cookie-string` 直接粘贴 Cookie 字符串），导出方法见
[references/workflow.md](references/workflow.md)。

输出与 B 站搜索同构的 JSON/CSV：资源名称、类型（电影/剧集）、大小、做种数、
下载数、下载链接（`/download/` 或 magnet/thunder 磁力链，VIP 资源标记为
`VIP可见`）。站点反爬敏感：脚本默认请求间隔 3 秒、失败退避重试，勿开并发。

**直连被反爬拦截时的备用路径**：在浏览器登录态下用油猴脚本「导出CSV」下载
文件，再导入（无需 Cookie、不受反爬影响）：

```bash
python scripts/import_moviejie_csv.py --csv 电影街_2026-08-16.csv \
  --out moviejie_export.json --csv-out moviejie_export.csv
```

### 1.6 YouTube / Twitch 采集（需代理/VPN）

```bash
python scripts/search_youtube.py --keyword "elden ring 战斗 混剪" --limit 10 \
  --out youtube.json --csv youtube.csv
python scripts/download_yt.py --search-json youtube.json --limit 3 --out-dir materials/yt
python scripts/download_yt.py --list-file clips.txt --out-dir materials/twitch
```

YouTube/Twitch 需要能访问外网的网络（本机开 VPN 时，采集命令须跑在宿主网络
下，不要在隔离沙箱里执行）。YouTube 搜索免登录；但 2026 年起下载普遍触发
`Sign in to confirm you're not a bot`，必须加 `--cookies youtube_cookies.txt`
（用 Get cookies.txt LOCALLY 导出 youtube.com 的登录 Cookie）；Twitch 片段
免登录。下载后同样 ffmpeg 规范化成 h264/aac MP4，产出 `download_manifest.json`，
可继续接 `clean_materials.py` 清洗与 `index_materials.py` 建索引。

### 1.7 A站 / 西瓜 / Mixkit 素材采集

```bash
# A站关键词搜索（匿名，首页 30 条/关键词）
python scripts/search_acfun.py --keyword "巫师3 战斗" --pages 2 \
  --out acfun.json --csv acfun.csv

# 西瓜视频关键词搜索（匿名易被 ByteDance 风控，Cookie 兜底）
python scripts/search_ixigua.py --keyword "巫师3" --cookies ixigua_cookies.txt \
  --out ixigua.json --csv ixigua.csv

# Mixkit 免登录直链素材（B-roll/转场/背景）
python scripts/collect_mixkit.py --category game --pages 2 \
  --out mixkit.json --csv mixkit.csv

# 批量下载（A站/西瓜统一走通用下载器，yt-dlp + ffmpeg 规范化）
python scripts/download_yt.py --search-json acfun.json --limit 5 --out-dir materials/acfun
python scripts/download_yt.py --search-json ixigua.json --cookies ixigua_cookies.txt \
  --out-dir materials/ixigua
```

要点：A站匿名可用、分页需浏览器会话（默认首页 30 条）；西瓜走
`ttwid + secsdk` 风控，匿名常返回页面壳，用浏览器导出的 `ixigua.com`
cookies.txt 兜底；Mixkit 免登录、直链 720p（`--quality 1080` 逐条校验），
授权为 Mixkit Restricted License。

### 2. 批量下载（两套方案）

**方案 A：yt-dlp（默认）**

```bash
python scripts/download_bilibili.py --search-json videos.json --limit 5 \
  --quality 720 --out-dir materials/witcher
python scripts/download_bilibili.py --url BV1px411o7jN --quality 720 --out-dir materials
python scripts/download_bilibili.py --list-file urls.txt --quality 480 --out-dir materials
```

内部用 yt-dlp 下载 + ffmpeg 规范化为 h264/aac `yuv420p` MP4（全平台/B 站可播）。
匿名最高 720p；要 1080p 及以上用 `--cookies cookies.txt`（Netscape 格式）。
`--section 0-15` 可只下载前 15 秒（测试或试看）。
产出 `download_manifest.json` 记录每个 BV 的文件路径。

**方案 B：API 直链下载（yt-dlp 遇 412 风控时用）**

```bash
python scripts/download_api.py --list-file urls.txt --out-dir materials
python scripts/download_api.py --url BV1px411o7jN --out-dir materials
```

走 B站官方 `view`/`playurl` 接口拿 720p 直链（匿名可用），ffmpeg 下载并规范化
为 MP4，自动跳过已下载文件并输出 `BV号.info.json` 元数据 + `api_manifest.json`。
当 yt-dlp 报 `HTTP 412 Precondition Failed`（网页抓取风控）时优先用此方案。

### 2.5 素材清洗（水印/字幕检测）

```bash
python scripts/clean_materials.py --dir materials --report watermark_report.json
python scripts/clean_materials.py --dir materials --crop-top 44 --out-dir materials_clean/
```

自动抽帧检测：右上角 UP 主水印（边缘密度比）与底部内嵌字幕（字幕比），
输出 JSON 报告标记嫌疑素材；`--crop-top N` 裁掉顶部水印区并放大回原尺寸。
采集后先跑检测，把带字幕/水印的素材清洗或剔除，避免进成片。

### 3. 弹幕与高能时刻

```bash
python scripts/fetch_danmaku.py --bvid BV1px411o7jN --out danmaku.json
python scripts/fetch_danmaku.py --cid 98999350 --window 5 --top 20 --csv danmaku.csv
```

输出全部弹幕（时间/颜色/文本）+ 按密度排序的高能时刻列表，
高能时间点可直接作为 `$beat-cut-sync` 的候选切点或选材依据。

### 4. 素材索引

```bash
python scripts/index_materials.py --dir materials --tag witcher --out index.json --csv index.csv
```

递归扫描下载目录，合并 yt-dlp 元数据（bvid/标题/UP 主）+ ffprobe
实测（时长/分辨率/大小），生成可检索的素材库索引。

## 衔接下游

- 索引里的视频直接跑 `$beat-cut-sync`：`detect_shots.py` 切镜头 → `align_cuts.py` 卡点。
- 视频里的对白跑 `$subtitle-review`：`transcribe.py` 转写 → 字幕 → 烧录 → 审阅。

接口细节、风控说明与常见问题见 [references/workflow.md](references/workflow.md)。

### 1.8 Yandex 图片搜索采集（封面图）

```bash
python scripts/collect_yandex_images.py --keyword "巫师3 重制版" --limit 10 --out-dir 封面/
python scripts/collect_yandex_images.py --keyword-file kw.txt --limit 8 --out-dir 封面/ --min-width 800
```

要点：只可用 `yandex.ru/images`（yandex.com 仅返回 JS 壳）；结果内嵌在搜索页 JSON
（`"origin":{"w":N,"h":N,"url":...}`），脚本自动解析原图直链并下载，产出 manifest.json；
带会话 Cookie 与 Referer，遇 SmartCaptcha 会报错。图源为第三方站点，商用/发布前自行确认版权。
