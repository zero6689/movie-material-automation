# B 站采集工作流详解

## 目录

- 输出目录约定
- 搜索接口与免登录原理
- 下载与清晰度说明
- 弹幕接口与高能时刻
- 素材索引字段
- 风控与常见问题
- 与卡点/字幕技能衔接

## 输出目录约定

素材与产物默认放在你指定的素材根目录下（本仓库不写死任何本机路径），
建议按项目隔离：

```text
<素材根目录>/<项目名>/
├─ videos.json / videos.csv        # 搜索列表
├─ <BV号>.mp4                      # 规范化成品
├─ <BV号>\.info.json               # yt-dlp 原始元数据
├─ download_manifest.json          # 下载清单
├─ danmaku.json / danmaku.csv      # 弹幕 + 高能时刻
└─ index.json / index.csv          # 素材库索引
```

## 搜索接口与免登录原理

使用 `https://api.bilibili.com/x/web-interface/search/type`：

```text
GET ?search_type=video&keyword=<关键词>&page=<页码>&order=<排序>
```

免登录的关键是匿名指纹 Cookie（buvid3/buvid4/buvid_fp/fingerprint/b_nut/
_uuid/b_lsid/sid/innersign）。缺少时会触发风控：旧接口 412，新接口只返回
`v_voucher` 而没有结果。脚本已内置完整 Cookie 组，直接可用。

搜索结果字段：`bvid`、`title`（含 `<em>` 高亮标签，脚本已清理）、`author`、
`duration`（秒）、`play`、`video_review`（弹幕数）、`pubdate`、`pic`（封面）。

## 下载与清晰度说明

内部调用 yt-dlp（`python -m yt_dlp`；可设 `YTDLP_CMD` 指向可执行文件）。

| 清晰度 | 匿名 | 说明 |
| --- | --- | --- |
| 360p / 480p / 720p | 可用 | 免登录直接下载 |
| 1080p / 高码率 | 需登录 | `--cookies cookies.txt`（Netscape 格式） |
| 4K / HDR / 杜比 | 需大会员 | 同 cookie 方案 |

下载后用 ffmpeg 统一规范化为 `libx264 + aac + yuv420p + faststart`，
保证所有剪辑软件与 B 站上传都能直接吃。`--no-normalize` 可跳过。
ffmpeg / ffprobe 通过 `PATH` 查找，也可用 `FFMPEG` / `FFPROBE` 环境变量指定。

## 弹幕接口与高能时刻

```text
GET https://api.bilibili.com/x/v1/dm/list.so?oid=<cid>
```

返回 XML `<d p="时间(ms),模式,字号,颜色,...">文本</d>`。
`--bvid` 会先调 `x/web-interface/view` 解析 cid、标题与 UP 主。

高能时刻 = 弹幕密度滑动窗口（默认 5 秒）前 N 名去重。适合：

- 找名场面/梗点做卡点素材
- 判断视频内容节奏（密集弹幕段 = 高潮段）

## 素材索引字段

`index_materials.py` 输出：

```json
{"count": 12, "dir": "...", "entries": [
  {"file": "...", "size_mb": 128.4, "duration": 1214.0, "resolution": "1920x1080",
   "bvid": "BV...", "title": "...", "uploader": "...", "tag": "witcher"}
]}
```

`--tag` 打标签，方便后续按项目/游戏/风格筛选。

## 风控与常见问题

- 搜索返回 412 或 `v_voucher`：检查网络出口；同一出口高频请求会触发验证码，
  放慢（脚本单线程）或换 Cookie。
- 下载 403/风控：加 `--cookies` 登录态 Cookie 通常可解。
- 中文关键词乱码：用 `--keyword-file` 传 UTF-8 文件，不要直接拼命令行。
- 下载很慢：yt-dlp 是单线程；需要并发可对 manifest 分片并行跑。
- 版权提醒：仅用于个人学习/二次创作素材收集，注意原作者授权与平台规则。
- Cookie 文件（cookies*.txt）属于登录凭据：只放本地、不要提交到仓库、不要打印。

## YouTube / Twitch 采集说明

### 网络前提：必须能访问外网

YouTube/Twitch 从部分网络不可达。本机开 VPN 后，命令要跑在 VPN 生效的
网络环境里执行（隔离沙箱可能走独立出口）。

### YouTube

搜索走 yt-dlp 的 `ytsearch`（免 API key、免登录），`search_youtube.py` 输出
与 B 站搜索同构的 JSON/CSV（id/title/channel/duration/url）。

2026 年起 YouTube 对下载普遍做风控（`Sign in to confirm you're not a bot`），
必须带登录 Cookie：

- 用 Get cookies.txt LOCALLY 扩展在 youtube.com 页面导出 `cookies.txt`；
- `download_yt.py --cookies youtube_cookies.txt ...`；
- 备选 `--cookies-from-browser edge`，但要求 Edge 处于关闭状态，运行中会报
  `Could not copy Chrome cookie database`。

清晰度：匿名通常 720p（部分 1080p）；带 Cookie 可稳定拿 1080p+。

### Twitch

片段（clip）与回放（VOD）链接免登录可直接下载：

```bash
python scripts/download_yt.py --list-file clips.txt --out-dir materials/twitch
```

每行一个 `https://www.twitch.tv/<频道>/clip/<ClipID>` 或
`https://www.twitch.tv/<频道>/videos/<VODID>` 链接。Twitch 没有开放搜索接口
（需 client id），用浏览器/站内搜索找到链接再批量下载。

### 片段下载与规范化

`--section 0-15` 先整段下载再用本地 ffmpeg 切割（yt-dlp 的
`--download-sections` 在部分格式上会报错，脚本会自动回退）。产物统一规范化为
`libx264 + aac + yuv420p + faststart`，`download_manifest.json` 记录
id/标题/频道/时长/文件路径，可直连清洗与索引。

## A站 / 西瓜 / Mixkit 采集说明

### A站（AcFun）

搜索走 BigPipe quickView 接口（匿名可用，无需登录）：

```text
GET /search?keyword=<关键词>&quickViewId=video-list&ajaxpipe=1&sortType=0
    &channelId=&type=video&keyword=<关键词>
Header: X-Requested-With: XMLHttpRequest
```

响应是若干 JSON 块，用 `/*<!-- fetch-stream -->*/` 分隔；块内 `html` 中的
`data-exposure-log` 含 `content_id`（acId）、标题、作者 id，
`video__duration` 给时长。脚本输出 id/title/author/duration/view_count/url。
注意：分页参数会被站点忽略（分页绑定浏览器会话），单关键词默认拿首页
30 条，够选材用。下载走 yt-dlp `AcFunVideo` 解器（已验证免登录）。

### 西瓜视频（Ixigua）

西瓜搜索与下载都过 ByteDance 风控（`ttwid` + `secsdk` 签名）：

- `search_ixigua.py` 会自动注册匿名 `ttwid` 再请求接口；
- 若仍返回页面壳而非 JSON（常见），加 `--cookies` 传浏览器导出的
  `ixigua.com` cookies.txt（Get cookies.txt LOCALLY 扩展）；
- 下载用 `download_yt.py --cookies ixigua_cookies.txt`，yt-dlp Ixigua
  解器无 Cookie 时会报 `Cookies are needed`。

### Mixkit（免费 B-roll 素材）

分类页 `https://mixkit.co/free-stock-video/<分类>/`（分页 `?page=N`）的卡片
带 `data-algolia-analytics-object-id="video-<id>"` 和标题；直链按 id 构造：

```text
https://assets.mixkit.co/videos/<id>/<id>-720.mp4   （默认）
https://assets.mixkit.co/videos/<id>/<id>-1080.mp4  （部分视频有，HEAD 校验）
```

`collect_mixkit.py` 默认收 720p 直链，`--quality 1080` 逐条 HEAD 校验后回落
720。素材为 Mixkit Restricted License，可免费用于个人/商业视频，商用场景
建议核对官网授权页。下载直链用 ffmpeg 或下载器直接拉取即可，不需要 yt-dlp。

## 与卡点/字幕技能衔接

```bash
# 卡点：先切镜头再对齐（需对应剪辑技能/脚本）
detect_shots.py --input 素材/BVxxx.mp4 --out shots.json
align_cuts.py --beats beats.json --shots shots.json --step 4 --out plan.json

# 字幕：转写 → ASS → 烧录 → 审阅（需对应字幕技能/脚本）
transcribe.py --input 素材/BVxxx.mp4 --lang zh --model tiny
```
