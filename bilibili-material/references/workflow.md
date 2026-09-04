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

按全局规则，素材默认放 V 盘：

```text
V:\CodexProjects\素材库\<项目名>\
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

内部调用 yt-dlp（`python -m yt_dlp`，包在
`V:\CodexProjects\witcher-world\python-libs`；也可设 `YTDLP_CMD` 覆盖）。

| 清晰度 | 匿名 | 说明 |
| --- | --- | --- |
| 360p / 480p / 720p | 可用 | 免登录直接下载 |
| 1080p / 高码率 | 需登录 | `--cookies cookies.txt`（Netscape 格式） |
| 4K / HDR / 杜比 | 需大会员 | 同 cookie 方案 |

下载后用 ffmpeg 统一规范化为 `libx264 + aac + yuv420p + faststart`，
保证所有剪辑软件与 B 站上传都能直接吃。`--no-normalize` 可跳过。

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

## 电影街（moviejie.net）采集

### 登录态是硬性要求

电影街整站登录墙：`/`、`/new/`（最新）、`/schedule/`、`/btbee/`、
`/subbee/`、`/door/`、`/user/rss/` 以及所有搜索/磁力结果页都会 302 到
`/user/login/`。唯一探到的免登录页面是 `/cili/`（磁力搜索入口），但它的
搜索结果同样要登录。油猴脚本能在浏览器里抓表格，是因为浏览器里有登录态。

`search_moviejie.py` 需要登录 Cookie 才能采集：

- `--cookies cookies.txt`：Netscape 格式。Chrome 装
  “Get cookies.txt LOCALLY”扩展，在 moviejie.net 页面导出即可。
- `--cookie-string "k=v; k2=v2"`：DevTools → Application → Cookies →
  moviejie.net 里复制 Cookie 字符串直接粘贴（注意整串都要带）。

### 页面结构与解析字段

解析逻辑与油猴脚本一致（`table tbody tr`）：

| 字段 | 选择器/位置 |
| --- | --- |
| 资源名称 | `.restitle`，自动去标签、去末尾 ↗ |
| 大小 | 行内第 2 个 `<td>` |
| 做种数 | `.seeders` |
| 下载数 | `.leechers` |
| 下载链接 | `a[href*="/download/"]` / `magnet:` / `thunder:`；无链接时标记 `VIP可见` / `无链接` |
| 类型 | 按名称关键词粗分 电影/剧集（season/ep/第/集/季/全/完/hdtv/webrip/S01E…） |

翻页跟随页面里的“下一页”链接自动解析，`--pages` 控制上限。

### 限流与稳定性

本站对高频探测会临时封 IP（表现为连接全部超时，约几分钟到更久后恢复）。
脚本默认每次请求间隔 3 秒、失败退避（3s/6s/12s）重试 3 次，请勿调小
`--delay` 或并发运行。被封后等 10 分钟以上再试。

### 下载说明

电影街给的是 BT/磁力/迅雷链接（`/download/` 跳转页、`magnet:`、`thunder:`），
不是直链视频。采集清单拿到磁力后，用 qBittorrent 等 BT 客户端下载成片，
再走 `clean_materials.py` 清洗和 `index_materials.py` 建索引，即可与 B 站素材
一样进入下游剪辑流程。

### 反爬拦截时的备用路径：油猴导出 CSV

站点对非浏览器流量很敏感（高频探测后会把出口 IP 的连接在 TCP 层丢包，
表现为 ConnectTimeout，持续几十分钟到几小时；浏览器登录态不受影响）。
此时不硬等，直接用浏览器里的油猴脚本点「📥 导出CSV」，把下载的文件交给
`import_moviejie_csv.py` 入库：

```bash
python scripts/import_moviejie_csv.py --csv 电影街_2026-08-16.csv \
  --out moviejie_export.json --csv-out moviejie_export.csv
```

支持一次传多个 CSV 合并去重（按 名称+链接）。注意：油猴脚本在列表页只能拿
到「无链接/VIP可见」标记，真正的磁力/下载链接需要登录后进资源详情页获取。

## YouTube / Twitch 采集说明

### 网络前提：必须能访问外网

YouTube/Twitch 从国内网络不可达。本机开 VPN 后，命令要跑在宿主网络下
（Codex 的执行沙箱走独立出口，VPN 不生效；沙箱里连 YouTube 会直接
ConnectTimeout，需在宿主网络/终端里运行脚本）。

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
python scripts/download_yt.py --list-file clips.txt --out-dir 素材库/twitch
```

每行一个 `https://www.twitch.tv/<频道>/clip/<ClipID>` 或
`https://www.twitch.tv/<频道>/videos/<VODID>` 链接。Twitch 没有开放搜索接口
（需 client id），用浏览器/站内搜索找到链接再批量下载。

### 片段下载与规范化

`--section 0-15` 先整段下载再用本地 ffmpeg 切割（yt-dlp 的
`--download-sections` 在部分格式上会报错，脚本会自动回退）。产物统一规范化为
`libx264 + aac + yuv420p + faststart`，`download_manifest.json` 记录
id/标题/频道/时长/文件路径，可直连 `clean_materials.py` 和 `index_materials.py`。

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
# 卡点：先切镜头再对齐
python <beat-cut-sync>/scripts/detect_shots.py --input 素材库/witcher/BVxxx.mp4 --out shots.json
python <beat-cut-sync>/scripts/align_cuts.py --beats beats.json --shots shots.json --step 4 --out plan.json

# 字幕：转写 → ASS → 烧录 → 审阅
python <subtitle-review>/scripts/transcribe.py --input 素材库/witcher/BVxxx.mp4 --lang zh --model tiny
```
