#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐刀包络尺子图：让用户按帧报「早了/晚了」。

每刀一行：缩略帧（切点 +0.35s）+ 300–3000Hz 包络 + 切点红线 + ±5/10/15 帧虚线刻度。
用户说「往后两格」= +2 帧（30fps 下 0.067s），比「有点早」好执行得多。

音轨直接从成片抽，切点也就直接用「成片时间」，不需要音频起点偏移。

用法：
  python cut_ruler.py --video 成片.mp4 --table 镜头表.md --out 包络尺子.jpg
  python cut_ruler.py --video 成片.mp4 --cuts 0.20,6.18,13.30 --out ruler.jpg

依赖 numpy scipy matplotlib，装进工程 venv（uv venv → uv pip install ...），别装系统 python。
ffmpeg 默认取 PATH，Windows 上通常要指 --ffmpeg "D:/Tools/VideoConverter/ffmpeg.exe"。
"""
import argparse
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np


def parse_table(path):
    """从镜头表 md 抽 (切点, 歌词)。列位置会变，按表头名定位，不按列序。"""
    rows, col_t, col_l = [], 1, 3
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if any(h in cells for h in ('切点', '切点（字头）')):
                for i, c in enumerate(cells):
                    if c.startswith('切点'):
                        col_t = i
                    if c.startswith('歌词'):
                        col_l = i
                continue
            if len(cells) <= col_t:
                continue
            try:
                t = float(cells[col_t])
            except ValueError:
                continue
            lyric = cells[col_l] if len(cells) > col_l else ''
            rows.append((t, lyric))
    return rows


def extract_wav(video, ffmpeg, out):
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', video,
                    '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000', out], check=True)


def envelope(y, sr, t0, t1):
    """10ms 窗、5ms 步长的 RMS（dB）。y 已是带通后的信号。"""
    n = int(0.01 * sr)
    ts, vs = [], []
    t = max(t0, 0.0)
    while t < t1:
        seg = y[int(t * sr):int(t * sr) + n]
        if len(seg) < n:
            break
        ts.append(t)
        vs.append(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9))
        t += 0.005
    return np.array(ts), np.array(vs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--table', help='镜头表 md（取「切点」列）')
    ap.add_argument('--cuts', help='或直接给逗号分隔的切点秒数')
    ap.add_argument('--out', default='包络尺子.jpg')
    ap.add_argument('--ffmpeg', default='ffmpeg')
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--window', type=float, default=0.55, help='切点两侧各取多少秒')
    args = ap.parse_args()

    if args.table:
        cuts = parse_table(args.table)
    elif args.cuts:
        cuts = [(float(v), '') for v in args.cuts.split(',') if v.strip()]
    else:
        sys.exit('给 --table 或 --cuts')
    if not cuts:
        sys.exit('没解析到切点，检查镜头表表头是否有「切点」列')

    from scipy.signal import butter, lfilter
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    tmp = tempfile.mkdtemp(prefix='ruler_')
    wavp = os.path.join(tmp, 'a.wav')
    extract_wav(args.video, args.ffmpeg, wavp)
    w = wave.open(wavp)
    sr = w.getframerate()
    y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    b, a = butter(4, [300 / (sr / 2), 3000 / (sr / 2)], btype='band')
    y = lfilter(b, a, y)          # 只滤一次，别在循环里重滤整轨

    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    n = len(cuts)
    ticks = [-15, -10, -5, 0, 5, 10, 15]
    fig = plt.figure(figsize=(15, 2.0 + n * 1.05))
    fig.patch.set_facecolor('#0e1216')
    gs = GridSpec(n, 2, width_ratios=[1.15, 4], figure=fig, hspace=0.95, wspace=0.05)

    for i, (t, lyric) in enumerate(cuts):
        thumb = os.path.join(tmp, 'f%d.jpg' % i)
        subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-ss', '%.3f' % (t + 0.35), '-i', args.video,
                        '-frames:v', '1', '-vf', 'scale=300:169', '-q:v', '3', thumb], check=False)
        ax = fig.add_subplot(gs[i, 0])
        try:
            ax.imshow(plt.imread(thumb))
        except Exception:
            pass
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color('#2b3540')
        ax.set_title('#%02d  %5.2fs  %s' % (i + 1, t, lyric), color='#e8eef5', fontsize=9.5, loc='left', pad=3)

        ts, v = envelope(y, sr, t - args.window, t + args.window)
        if not len(ts):
            continue
        rel = (ts - t) * args.fps
        ax2 = fig.add_subplot(gs[i, 1])
        ax2.plot(rel, v, color='#5ad1ff', lw=1.3)
        ax2.axvline(0, color='#ff4d6d', lw=2.2)
        for k in ticks:
            if k:
                ax2.axvline(k, color='#ff4d6d', lw=0.5, alpha=0.3, ls=':')
        ax2.axvspan(-1, 1, color='#ff4d6d', alpha=0.18)
        ax2.set_xlim(-16.5, 16.5)
        ax2.set_ylim(v.min() - 2, v.max() + 4)
        ax2.set_yticks([])
        ax2.grid(alpha=0.10, color='#7b8a99')
        for sp in ax2.spines.values():
            sp.set_color('#2b3540')
        ax2.set_xticks(ticks)
        if i == n - 1:
            ax2.set_xticklabels([('%+d' % k) if k else '0' for k in ticks], fontsize=7.5, color='#7b8a99')
            ax2.set_xlabel('相对切点的帧数（红线 = 当前切点；说「往后两格」= +2 帧）',
                           color='#9fb0bf', fontsize=9, labelpad=2)
        else:
            ax2.set_xticklabels([])

    fig.suptitle('逐刀包络尺子（红线 = 当前切点，虚线 = ±5/10/15 帧）',
                 color='#e8eef5', fontsize=13.5, x=0.012, ha='left', y=0.997)
    fig.savefig(args.out, dpi=115, facecolor=fig.get_facecolor(), bbox_inches='tight')
    print('ok %s  刀数 %d' % (args.out, n))


if __name__ == '__main__':
    main()
