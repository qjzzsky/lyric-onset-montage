#!/usr/bin/env python3
"""求解「成片 0 秒 = 原曲第几秒」——音频时间基准对齐。

为什么必须有这一步：镜头表用成片秒，原曲 / LRC 用原曲秒，两者差一个起点偏移
（剪掉开头数字静音、只取副歌段、素材倒序都会引入）。不先解出来，逐句对表会整体
漂几百毫秒到几十秒，看着像「算法全废」。任何跨「镜头表 / 原曲 / LRC / 外部标尺」
的比数，都先跑这个。

做法：两边解码成 16k 单声道 → 10ms RMS 包络 → 拿成片开头一段（默认 60s）在原曲
包络上滑窗做归一化互相关 → 最优 lag 即偏移 → 再在 ±0.3s 内按 1ms 细化。

用法：
  python solve_audio_offset.py 原曲.mp3 成片.mp4
  python solve_audio_offset.py 原曲.m4a 成片.mp4 --template 90 \
      --ffmpeg /path/to/ffmpeg

判读：
  · 相关度 > 0.9 才算解对，0.95 以上很稳（实测工程里多为 0.98–0.9995）。
  · 最优与次优峰差 < 0.05 说明有歧义（重复副歌 / 循环段），换 --template 长度或
    起点重跑，别直接用。
  · 成片只覆盖原曲一段（如 98s 断句版 vs 287s 原曲）也能解；输出的「可对表范围」
    就是成片时长，超出这段的歌词不参与对表。
  · 只依赖 numpy + ffmpeg；没有 ffprobe 也能跑（时长从解码后的 wav 算）。
"""
import argparse
import os
import shutil
import subprocess
import tempfile
import wave

import numpy as np

SR = 16000


def decode(path, ffmpeg, out_wav):
    """解码成 16k 单声道 wav，返回 (float 采样, 时长秒)。"""
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", path, "-vn",
         "-ac", "1", "-ar", str(SR), out_wav],
        check=True,
    )
    with wave.open(out_wav, "rb") as f:
        n = f.getnframes()
        raw = f.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0, n / float(SR)


def envelope(x, hop):
    n = len(x) // hop
    return np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)


def _norm(v):
    v = v - v.mean()
    return v / (v.std() + 1e-9)


def scan(base, tmpl, lo, hi):
    """在 base 上滑 tmpl，返回 (最优, 次优) 各为 (r, lag)。"""
    t = _norm(tmpl)
    L = len(t)
    hi = min(hi, len(base) - L)
    lo = max(0, lo)
    best, second = (-2.0, 0), (-2.0, 0)
    for lag in range(lo, hi + 1):
        r = float((_norm(base[lag:lag + L]) * t).mean())
        if r > best[0]:
            second, best = best, (r, lag)
        elif r > second[0]:
            second = (r, lag)
    return best, second


def solve(song, cut, ffmpeg, template_s=60.0):
    tmp = tempfile.mkdtemp(prefix="offset_")
    try:
        xs, dur_s = decode(song, ffmpeg, os.path.join(tmp, "song.wav"))
        xc, dur_c = decode(cut, ffmpeg, os.path.join(tmp, "cut.wav"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 粗扫：10ms 包络
    eS, eC = envelope(xs, 160), envelope(xc, 160)
    n_t = max(20, min(len(eC), int(template_s * 100)))
    (r1, l1), (r2, l2) = scan(eS, eC[:n_t], 0, len(eS) - n_t)

    # 细化：1ms 包络，只在粗扫结果 ±0.3s 内
    fS, fC = envelope(xs, 16), envelope(xc, 16)
    center = int(round(l1 * 10))
    (rf, lf), (rf2, _) = scan(fS, fC[: n_t * 10], center - 300, center + 300)

    return dict(
        offset=lf / 1000.0, r=rf, r2=rf2,
        offset_coarse=l1 / 100.0, r_coarse=r1,
        dur_song=dur_s, dur_cut=dur_c,
    )


def main():
    ap = argparse.ArgumentParser(description="求解成片↔原曲的音频起点偏移")
    ap.add_argument("song", help="原曲 / 参考音轨（mp3 / m4a / wav）")
    ap.add_argument("cut", help="成片（mp4）")
    ap.add_argument("--template", type=float, default=60.0, help="模板长度秒，默认 60")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件路径")
    a = ap.parse_args()

    r = solve(a.song, a.cut, a.ffmpeg, a.template)
    print("原曲 %.2fs   成片 %.2fs" % (r["dur_song"], r["dur_cut"]))
    print("成片 0s = 原曲 %.3fs   r=%.4f  (次优 %.4f)"
          % (r["offset"], r["r"], r["r2"]))
    print("成片覆盖原曲 %.2f–%.2fs（可对表范围）"
          % (r["offset"], r["offset"] + r["dur_cut"]))
    if r["r"] < 0.9:
        print("⚠ 相关度 <0.9：没解对。换 --template 长度/起点，或确认两条轨是同一版本。")
    if r["r"] - r["r2"] < 0.05:
        print("⚠ 最优与次优峰太近：有歧义（重复段）。换模板重跑，别直接用。")


if __name__ == "__main__":
    main()
