# -*- coding: utf-8 -*-
"""四角边缘密度 profile：定位左上/右上水印纵向范围，对比中部密度。
用法: python corner_probe.py <img...>
输出: 每图 top-left/top-right/bottom-left/bottom-right 的纵向峰值 + 顶带/中带密度比。
"""
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

def band_density(a, x0, x1, y0, y1):
    reg = a[y0:y1, x0:x1]
    return float(np.abs(np.diff(reg, axis=1)).mean())

for path in sys.argv[1:]:
    a = np.asarray(Image.open(path).convert("L")).astype(float)
    h, w = a.shape
    mid = band_density(a, int(w * 0.3), int(w * 0.7), int(h * 0.3), int(h * 0.7))
    print(f"== {path} ({w}x{h}) mid={mid:.2f} ==")
    for corner, x0, x1 in [("TL", 0, int(w * 0.26)), ("TR", int(w * 0.74), w)]:
        reg = a[:, x0:x1]
        row_grad = np.abs(np.diff(reg, axis=1)).mean(axis=1)
        top = float(row_grad[: int(h * 0.22)].mean())
        print(f"  {corner} top22%={top:.2f} ratio={top / max(mid, 0.1):.2f}")
        peaks = []
        for y in range(0, h, 5):
            v = float(row_grad[y:y + 5].mean())
            if v > max(mid * 1.5, 1.5):
                peaks.append(f"y{y}-{y + 4}:{v:.1f}")
        print("    peaks: " + (" | ".join(peaks[:50]) if peaks else "none"))
