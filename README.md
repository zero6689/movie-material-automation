# movie-material-automation

电影素材每日采集自动化的**可复用脚本包**。
本仓库发布的是脚本与文档，不含任何个人素材、密钥、Cookie 或运行产物；
代码与文档不绑定任何本机绝对路径，复制到任何目录即可使用。

## 目录

- `bilibili-material/`：素材采集脚本与说明
  - 搜索：B站 / A站 / 西瓜 / YouTube / Mixkit / Yandex 图片
  - 下载：yt-dlp 封装（B站 / YouTube / Twitch / A站 / 西瓜）与 B站 API 直链兜底
  - 处理：水印/字幕检测与清洗、弹幕高能时刻、素材索引
- `movie_work/`：电影线辅助脚本（合并过滤、精选、水印裁剪、索引增强、文案生成调用）
- `automation.example.toml`：脱敏后的自动化配置模板
- `.gitignore`：密钥 / Cookie / 素材 / 产物排除清单

## 运行前提

- Python 3.10+，依赖：`requests`、`Pillow`、`numpy`
- 外部工具：`ffmpeg` / `ffprobe` / `yt-dlp`
  - 加入 `PATH`，或分别用 `FFMPEG`、`FFPROBE`、`YTDLP_CMD` 环境变量指定
- API 密钥只从环境变量或项目 `.env` 读取；**禁止把 `.env` / cookies 提交或打印**

## 常用命令

```bash
# 搜索（中文关键词建议用文件传入，避免编码问题）
python bilibili-material/scripts/search_bilibili.py --keyword-file kw.txt \
  --pages 2 --order pubdate --out search.json --csv search.csv

# 下载（yt-dlp 方案；遇 412 风控改用 API 直链）
python bilibili-material/scripts/download_bilibili.py --list-file urls.txt \
  --quality 720 --out-dir bilibili/
python bilibili-material/scripts/download_api.py --list-file urls.txt --out-dir bilibili/

# 清洗：先出检测报告，再按报告裁顶部水印
python bilibili-material/scripts/clean_materials.py --dir bilibili/ --report wm.json
python movie_work/clean_single.py --in bilibili/BVxxxx.mp4 --out clean/ --crop-top 66

# 弹幕高能时刻 + 索引
python bilibili-material/scripts/fetch_danmaku.py --bvid BV1xxxx --out danmaku.json
python bilibili-material/scripts/index_materials.py --dir clean/ \
  --tag movie --out index.json --csv index.csv
```

详细工作流见 `bilibili-material/references/workflow.md` 与 `SKILL.md`。

## 安全说明

- 仓库内无任何 API 密钥或 Cookie；`automation.example.toml` 已脱敏，
  不包含本机路径、项目 UUID 或调度配置的私有字段。
- 下载器只接受白名单域名与合法视频 ID，拒绝 `-` 开头行（防 yt-dlp 选项注入）；
  Yandex 采集启用 TLS 校验并限制图片类型与大小；CSV 导出已做公式注入转义。
- 上传/克隆本仓库后请先执行一次自查，确保 0 命中：
  `rg -n "sk-[A-Za-z0-9]|AKIA|AIza|ghp_|verify=False" .`

## 免责

脚本仅用于个人学习/二次创作素材收集；发布成片前请遵守各平台规则与版权约定。
