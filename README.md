# movie-material-automation

电影素材每日采集自动化的**可发布脚本包**（面向 GitHub Pages / 公开仓库）。
本包由 `automation-2`（每日电影素材采集 + 清洗 + 方向文案）引用的脚本整理而来，
并已按 2026-09-04 安全扫描（report: `.security-scans/automation-2-movie-daily/scan_20260904_220738/report.md`）
完成硬化。

## 目录

- `bilibili-material/`：素材采集技能（B站/A站/电影街/西瓜/YouTube/Mixkit/Yandex 的搜索、下载、清洗、弹幕、索引脚本）
- `movie_work/`：电影线每日辅助脚本（合并过滤/精选/水印裁剪/索引增强/DeepSeek 文案）
- `automation.example.toml`：脱敏后的自动化配置模板（不要直接提交本机 automation.toml）
- `.gitignore`：密钥/素材/产物排除清单（先于任何 git add 生效）

## 运行前提（不含本机私有配置）

- Python 3.10+，依赖：`requests`、`PIL`、`numpy`
- 外部工具：`ffmpeg` / `ffprobe` / `yt-dlp`
  - 可通过环境变量指定：`FFMPEG`、`FFPROBE`、`YTDLP_CMD`
  - 未设置时脚本回退到本机历史路径（仅兼容原作者环境；公开使用请设置环境变量）
- API 密钥只从环境变量或 `<项目根>/.env` 读取；**禁止把 .env/cookies 提交或打印**

## 安全硬化清单（2026-09-04）

1. `collect_yandex_images.py`：移除全部 `verify=False`；只接受 https 图片目标；下载前校验 Content-Type 为 image/* 并限制 30MB 大小。
2. 下载器输入校验：
   - `download_bilibili.py` / `download_api.py`：只接受纯 BV 号或 `https://www.bilibili.com/video/BV...`；输出文件名由 BV 正则提取，杜绝路径穿越。
   - `download_yt.py`：仅接受 https 且主机在 youtube/youtu.be/twitch/acfun/ixigua 白名单；输出 id 限定安全字符集。
   - 三个下载器都拒绝 `-` 开头行（防 yt-dlp 选项注入）。
3. CSV 公式注入：所有 CSV 导出对文本单元格做 `= + - @` 前缀转义（`csv_cell`），机器消费请优先 JSON。
4. 发布排除：`.env`、`cookies*.txt`、素材/日报/索引/弹幕数据、`__pycache__`、`.security-scans` 一律不进仓库（见 `.gitignore`）。
5. `automation.example.toml` 已脱敏：不含机器绝对路径、Codex 项目 UUID、cwds；密钥只保留变量名约定。

## 使用说明（摘要）

```powershell
# 搜索
python bilibili-material/scripts/search_bilibili.py --keyword-file kw.txt --pages 2 --order pubdate --out search.json
# 下载（yt-dlp 412 时用 API 直链）
python bilibili-material/scripts/download_bilibili.py --list-file urls.txt --quality 720 --out-dir bilibili/
python bilibili-material/scripts/download_api.py --list-file urls.txt --out-dir bilibili/
# 清洗（先 --report 后 crop）
python bilibili-material/scripts/clean_materials.py --dir bilibili/ --report wm.json
python movie_work/clean_single.py --in <file> --out clean/ --crop-top 66
# 弹幕高能 + 索引
python bilibili-material/scripts/fetch_danmaku.py --bvid BV1xxxx --out danmaku.json
python bilibili-material/scripts/index_materials.py --dir clean/ --tag movie --out index.json --csv index.csv
```

电影线完整编排见自动化指令（report.md/directions.md/copy.md 输出环节），本仓库只放可复用脚本，不承载个人素材。

## 免责

脚本仅用于个人学习/二次创作素材收集；发布前请遵守各平台规则与版权约定（见 `bilibili-material/references/workflow.md` 风控与版权提醒）。
