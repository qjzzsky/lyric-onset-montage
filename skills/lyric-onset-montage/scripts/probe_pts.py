# -*- coding: utf-8 -*-
"""候选入点探针：一条素材给几个时间点，出一张带秒数标签的拼图，视觉一次读完定位真窗口。

为什么需要它：素材索引/清单里的「黄金窗口」常是粗查误判（写「机器狗」实为走廊、
写「大旗特写」实为屋檐）。逐点抽帧再逐次问视觉模型很贵；一条素材 6 个点拼一图，一眼定位。

用法：
  python probe_pts.py 素材.mp4 0,5,10,20,30,45 out.jpg
  python probe_pts.py 素材.mp4 1240-1290:6 out2.jpg        # 区间等分 6 点

输出图左上是黄色时间戳，格子按 3 列排。
"""
import os
import subprocess
import sys


def parse_times(spec):
    if "-" in spec and "," not in spec:
        rng, n = spec.split(":")
        a, b = (float(v) for v in rng.split("-"))
        n = int(n)
        return [round(a + (b - a) * i / max(1, n - 1), 2) for i in range(n)]
    return [float(v) for v in spec.split(",") if v.strip()]


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    src, spec, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ff = os.environ.get("FFMPEG", "ffmpeg")
    times = parse_times(spec)

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("需要 Pillow：pip install pillow")

    tiles = []
    for t in times:
        p = subprocess.run([ff, "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                            "-vf", "scale=360:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if p.returncode != 0 or not p.stdout:
            print(f"# {t:.2f}s 抽帧失败", file=sys.stderr)
            continue
        import io
        im = Image.open(io.BytesIO(p.stdout)).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 78, 18], fill=(0, 0, 0))
        d.text((3, 4), f"{t:.2f}s", fill=(255, 255, 0))
        tiles.append(im)

    if not tiles:
        sys.exit("一帧都没抽到，检查路径与时间点")
    cols = 3
    cw, ch = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), (0, 0, 0))
    for k, im in enumerate(tiles):
        sheet.paste(im, ((k % cols) * cw, (k // cols) * ch))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    sheet.save(out, quality=88)
    print(f"# {out}  {sheet.size[0]}x{sheet.size[1]}  {len(tiles)} 格：{','.join(f'{t:g}' for t in times)}")


if __name__ == "__main__":
    main()
