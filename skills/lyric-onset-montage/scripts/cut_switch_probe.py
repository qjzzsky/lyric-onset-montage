"""切点实测：从成片抽每个切点前 5 帧起共 11 帧，帧差扫描定「实测换镜帧」。

用法：
    python cut_switch_probe.py --video 成片.mp4 --cuts 6.77,23.75,41.44,47.72
    python cut_switch_probe.py --video 成片.mp4 --cuts 3:6.77,8:23.75   # 带刀号

输出：刀号 | 规格切点 | 实测换镜帧 | 实测秒 | 差(s)。多刀挪切点的交付附这张表。
换镜帧 = 相邻帧平均绝对差最大处的后一帧；只从成片实测，不引用计划值。
依赖：numpy；ffmpeg 在 PATH（或 --ffmpeg 给绝对路径）。
"""
import argparse
import subprocess
import sys


def probe(ffmpeg, video, t, fps, win):
    import numpy as np   # 延后导入：--help 不需要 numpy

    n = 2 * win + 1
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{t - win / fps:.4f}", "-i", video,
         "-frames:v", str(n), "-vf", "scale=160:90", "-pix_fmt", "gray",
         "-f", "rawvideo", "-"],
        capture_output=True).stdout
    need = n * 90 * 160
    if len(raw) < need:
        return None
    fr = np.frombuffer(raw[:need], np.uint8).reshape(n, 90, 160).astype(np.int16)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    k = int(np.argmax(d))               # 第 k 对相邻帧差异最大 → 换镜在 k 与 k+1 之间
    return round(t * fps) - win + k + 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--cuts", required=True,
                    help="逗号分隔的切点秒：6.77,23.75，或带刀号 3:6.77,8:23.75")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--win", type=int, default=5, help="切点前后各取几帧")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()

    try:
        import numpy  # noqa: F401   # 放在解析参数之后：--help / --version 不需要 numpy
    except ImportError:
        sys.exit("缺 numpy：pip install numpy（或 uv run --with numpy python cut_switch_probe.py ...）")

    print("刀号  规格切点  实测换镜帧  实测秒  差(s)")
    for i, tok in enumerate(a.cuts.split(","), 1):
        tok = tok.strip()
        no, ts = tok.split(":", 1) if ":" in tok else (str(i), tok)
        t = float(ts)
        frame = probe(a.ffmpeg, a.video, t, a.fps, a.win)
        if frame is None:
            print(f"{no:>4}  {t:>8.2f}  抽帧不足（切点太靠片头/片尾？）", file=sys.stderr)
            continue
        tm = frame / a.fps
        print(f"{no:>4}  {t:>8.2f}  {frame:>9}  {tm:>6.2f}  {tm - t:+.2f}")


if __name__ == "__main__":
    main()
