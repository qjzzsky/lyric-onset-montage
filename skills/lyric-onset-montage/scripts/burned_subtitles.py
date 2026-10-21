# -*- coding: utf-8 -*-
"""烧录字幕（MV 硬字幕）检测：定句界 + 出可读拼图。

为什么需要它：影视/儿童主题曲的 MV 常把歌词烧在画面里，而这类片子往往没有可用字幕轨。
这时烧录字幕就是「歌词文本 + 句界」最可靠的来源（网络歌词站是二手拼接版）。

用法：
  python burned_subtitles.py 视频.mp4                        # 自检：自动挑字幕带，打印每段起止秒
  python burned_subtitles.py 视频.mp4 --band 412:62 --thr 1200 --tile out/sub   # 出每段中点拼图

  --band y:h   字幕带（不写则扫 6 条横带，选「开/关红色像素量对比最大」那条）
  --x x:w      横向范围（默认整宽；只框画面中央可避开台标/水印）
  --thr N      判「有字幕」的红色像素阈值（默认 1200；852x480 上实测中位 390 / p90 5901）
  --tile P     每段取中点一帧，拼成带序号+起始秒的图，交给视觉模型逐格读字

输出：每段「序号 / 起秒 / 止秒 / 时长」，以及疑似「同类无字帧」提示。
注意：相邻两行只差一个字时像素量几乎不变，本脚本检不出换行，
     必须再按 1 秒抽帧用眼睛确认（见 references/lyric-timing.md 第一节）。
"""
import argparse
import os
import subprocess
import sys

import numpy as np


def decode_band(ff, vid, y, h, x, w, fps=10):
    """按 fps 抽帧、裁字幕带、缩一半宽，返回 (T, H, W, 3) uint8。"""
    vf = f"crop={w}:{h}:{x}:{y},scale=iw/2:ih/2,fps={fps}"
    p = subprocess.run([ff, "-v", "error", "-i", vid, "-vf", vf,
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    if p.returncode != 0:
        sys.exit(p.stderr.decode("utf-8", "replace")[-2000:])
    fsz = (w // 2) * (h // 2) * 3
    n = len(p.stdout) // fsz
    return np.frombuffer(p.stdout[:n * fsz], np.uint8).reshape(n, h // 2, w // 2, 3), fps


def red_count(arr):
    """红色字（纯红填充或红描边）的像素量：允许少量串色，只要够红。"""
    r, g, b = arr[..., 0].astype(np.int16), arr[..., 1].astype(np.int16), arr[..., 2].astype(np.int16)
    m = (r > 150) & (g < 75) & (b < 75)
    return int(m.sum())


def segments(cnt, thr, fps):
    on = cnt > thr
    segs, i, n = [], 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            segs.append((i / fps, (j + 1) / fps, j - i + 1))
            i = j + 1
        else:
            i += 1
    return segs


def autoband(ff, vid, h_probe=480):
    """扫 6 条横带，取「on 帧红色量 / off 帧红色量」比值最大的。"""
    best = None
    for y in range(0, int(h_probe * 0.8), int(h_probe * 0.8) // 6 or 1):
        arr, _ = decode_band(ff, vid, y, 70, 0, 852)
        c = np.array([red_count(a) for a in arr])
        if len(c) < 10:
            continue
        hi, lo = np.percentile(c, 90), np.percentile(c, 10)
        ratio = hi / max(1.0, lo)
        if best is None or ratio > best[0]:
            best = (ratio, y, hi, lo)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--band", default=None, help="y:h，例如 412:62")
    ap.add_argument("--x", default="0:852", help="x:w，例如 150:560")
    ap.add_argument("--thr", type=int, default=1200)
    ap.add_argument("--tile", default=None)
    a = ap.parse_args()

    if a.band:
        y, h = (int(v) for v in a.band.split(":"))
        band_note = f"--band {a.band}"
    else:
        r = autoband(a.ffmpeg, a.video)
        if r is None:
            sys.exit("没扫到字幕带，手动给 --band y:h")
        print(f"# 自动选带 y={r[1]} (on/off 比 {r[0]:.1f}, p90={r[2]:.0f} p10={r[3]:.0f})", file=sys.stderr)
        y, h = r[1], 70
        band_note = f"--band {y}:{h}"
    x, w = (int(v) for v in a.x.split(":"))

    arr, fps = decode_band(a.ffmpeg, a.video, y, h, x, w)
    cnt = np.array([red_count(f) for f in arr])
    segs = segments(cnt, a.thr, fps)
    print(f"# band={band_note} x={a.x} thr={a.thr} fps={fps} 帧数={len(cnt)}")
    print(f"# p50={np.percentile(cnt,50):.0f} p90={np.percentile(cnt,90):.0f} max={cnt.max()}")
    print(f"# 段数={len(segs)}")
    print("# idx   起     止    时长")
    for k, (t0, t1, _) in enumerate(segs, 1):
        warn = "  ⚠<0.8s" if t1 - t0 < 0.8 else ""
        print(f"  {k:3d} {t0:7.2f} {t1:7.2f} {t1-t0:6.2f}{warn}")

    if a.tile:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            sys.exit("出图需要 Pillow：pip install pillow")
        os.makedirs(os.path.dirname(a.tile) or ".", exist_ok=True)
        tiles = []
        for k, (t0, t1, _) in enumerate(segs, 1):
            mid = (t0 + t1) / 2
            i = min(len(arr) - 1, int(mid * fps))
            im = Image.fromarray(arr[i]).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 96, 18], fill=(0, 0, 0))
            d.text((3, 4), f"{k}: {t0:.2f}s", fill=(0, 255, 0))
            tiles.append(im)
        cols = 2
        cw, ch = tiles[0].size
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cw * cols, ch * rows), (0, 0, 0))
        for k, im in enumerate(tiles):
            sheet.paste(im, ((k % cols) * cw, (k // cols) * ch))
        out = a.tile + f"_tile_{1 if rows <= 20 else 1}.jpg"
        sheet.save(out, quality=88)
        print(f"# 拼图 -> {out}  {sheet.size[0]}x{sheet.size[1]}，{len(tiles)} 格")
        if rows > 20:
            print("# 格数多，建议 --band/--x 收窄后分批出图，或把该 jpg 直接交给视觉模型逐格读")


if __name__ == "__main__":
    main()
