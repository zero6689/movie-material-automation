# -*- coding: utf-8 -*-
"""DeepSeek 生成电影方向+文案；输出到 directions_draft.txt（人工校正后写入 directions.md/copy.md）。"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
WORK = os.path.dirname(os.path.abspath(__file__))

KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not KEY:
    raise SystemExit("DEEPSEEK_API_KEY 未注入")

prompt = open(os.path.join(WORK, "prompt_directions.txt"), encoding="utf-8").read()
body = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.7,
    "max_tokens": 6000,
}
req = urllib.request.Request(
    "https://api.deepseek.com/chat/completions",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
)
with urllib.request.urlopen(req, timeout=300) as resp:
    data = json.load(resp)
text = data["choices"][0]["message"]["content"]
with open(os.path.join(WORK, "directions_draft.txt"), "w", encoding="utf-8") as f:
    f.write(text)
print(text[:2000])
