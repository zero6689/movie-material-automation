# -*- coding: utf-8 -*-
"""清洗验证：裁剪后帧 vs 原帧。
- 顶带梯度应显著下降（水印被裁掉）
- 底带梯度应基本一致（字幕保留）
- 全图相关性应高（内容未被破坏）
用法: python verify_crop.py <orig_dir> <clean_dir> <crop> <name...>
"""
import os
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


def grad(a, y0, y1, x0=None, x1=None):
    h, w = a.shape
    x0 = x0 or 0
    x1 = x1 or w
    return float(np.abs(np.diff(a[y0:y1, x0:x1], axis=1)).mean())


orig_dir, clean_dir, crop = sys.argv[1], sys.argv[2], int(sys.argv[3])
for name in sys.argv[4:]:
    for i in (0, 1, 2):
        o = np.asarray(Image.open(os.path.join(orig_dir, f"{name}_{i}.png")).convert("L")).astype(float)
        c = np.asarray(Image.open(os.path.join(clean_dir, f"{name}_{i}.png")).convert("L")).astype(float)
        h, w = o.shape
        top_o = grad(o, 0, crop)
        top_c = grad(c, 0, crop)
        bot_o = grad(o, int(h * 0.86), h)
        bot_c = grad(c, int(h * 0.86), h)
        corr = float(np.corrcoef(o.ravel(), c.ravel())[0, 1])
        print(f"{name}_{i}: top_grad {top_o:.2f}->{top_c:.2f} (drop {100*(1-top_c/max(top_o,1e-6)):.0f}%) | "
              f"bottom_grad {bot_o:.2f}->{bot_c:.2f} | corr {corr:.4f}")
