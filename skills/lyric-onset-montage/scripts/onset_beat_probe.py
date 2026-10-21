# -*- coding: utf-8 -*-
"""谱通量起音 + 拍网格 + 切点对照，输出 JSON。

用法：
  python onset_beat_probe.py <音频> [--cuts 46.91,51.13,54.05] [--json out.json]

输出（JSON）：
  bpm / period / beats[] / onsets[] / cuts[{cut, onset, onset_diff_ms, beat, beat_diff_ms}] / stats

口径：
  onset_diff_ms = (切点 - 实测字头) * 1000          # 刀准不准
  beat_diff_ms  = (切点 - 最近拍点) * 1000          # 这一刀离拍点有多远
  stats 里的 B 用「字头 vs 最近拍点」算，和主指标分开报。
"""
import argparse
import json
import os
import subprocess
import wave

import numpy as np
from scipy.signal import find_peaks


def load_wav(path, tmp_wav=None):
    """非 wav 先用 ffmpeg 转 22.05k 单声道。返回 (samples, sr)。"""
    if not path.lower().endswith(".wav"):
        tmp_wav = tmp_wav or os.path.join(os.path.dirname(os.path.abspath(path)),
                                          "_probe_16k.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path,
                        "-ac", "1", "-ar", "22050", tmp_wav], check=True)
        path = tmp_wav
    with wave.open(path) as w:
        sr = w.getframerate()
        sig = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return sig.astype(np.float32) / 32768.0, sr


def spectral_flux(sig, sr, hop=128, win=1024):
    """谱通量包络归一化到 0–1，返回 (flux, t, 帧包络)。"""
    frames = 1 + (len(sig) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(frames)[:, None]
    S = np.abs(np.fft.rfft(sig[idx] * np.hanning(win), axis=1))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    flux /= (flux.max() + 1e-9)
    return flux, np.arange(len(flux)) * hop / sr


def estimate_tempo(flux, fps, lo=55, hi=180):
    """自相关估 tempo（BPM）。峰值做抛物线插值取亚采样 lag：
    1 帧的 lag 量化在 5 分钟的曲子上会让网格漂出好几秒，相位 R 直接归零。"""
    x = flux - flux.mean()
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    lags = np.arange(len(ac)) / fps
    m = (lags > 60 / hi) & (lags < 60 / lo)
    k = int(np.argmax(np.where(m, ac, -1e18)))
    if 0 < k < len(ac) - 1:
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
        den = y0 - 2 * y1 + y2
        if abs(den) > 1e-12:
            k = k + 0.5 * (y0 - y2) / den
    return 60 / (k / fps)


def beat_grid(flux, fps, dur, bpm):
    """相位扫描：让网格尽量压在能量峰上。"""
    period = 60 / bpm
    n = len(flux)
    best_phase, best_score = 0.0, -1.0
    for ph in np.arange(0, period, 0.01):
        idx = np.round(np.arange(ph, dur, period) * fps).astype(int)
        idx = idx[(idx >= 0) & (idx < n)]  # 末拍索引可能正好等于数组长度，越界会 IndexError
        sc = float(flux[idx].sum()) if len(idx) else 0.0
        if sc > best_score:
            best_phase, best_score = ph, sc
    return np.arange(best_phase, dur, period)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--cuts", default="", help="逗号分隔的成片切点秒数")
    ap.add_argument("--json", default="probe.json")
    ap.add_argument("--peak-height", type=float, default=0.10)
    a = ap.parse_args()

    sig, sr = load_wav(a.audio)
    dur = len(sig) / sr
    flux, t = spectral_flux(sig, sr)
    bpm = estimate_tempo(flux, sr / 128)
    beats = beat_grid(flux, sr / 128, dur, bpm)

    peaks, props = find_peaks(flux, height=a.peak_height, distance=int(0.16 * sr / 128))
    onsets = t[peaks]

    cuts = [float(x) for x in a.cuts.split(",") if x.strip()]
    rows = []
    for c in cuts:
        on = float(onsets[np.argmin(np.abs(onsets - c))])
        bt = float(beats[np.argmin(np.abs(beats - c))])
        rows.append({"cut": c, "onset": round(on, 3),
                     "onset_diff_ms": round((c - on) * 1000),
                     "beat": round(bt, 3),
                     "beat_diff_ms": round((c - bt) * 1000)})

    if cuts:
        on_d = np.array([abs(r["onset_diff_ms"]) for r in rows])
        # 同基准对照：拿「字头」比最近拍点，不要用切点比拍点
        bt_d = np.array([abs(float(beats[np.argmin(np.abs(beats - r["onset"]))]) - r["onset"])
                         for r in rows]) * 1000
        stats = {"n": len(rows),
                 "onset_median_ms": float(np.median(on_d)),
                 "onset_max_ms": float(on_d.max()),
                 "grid_median_ms": float(np.median(bt_d)),
                 "grid_max_ms": float(bt_d.max())}
    else:
        stats = None

    out = {"sr": sr, "duration": round(dur, 3), "bpm": round(bpm, 2),
           "period": round(60 / bpm, 3),
           "beats": [round(b, 3) for b in beats.tolist()],
           "onsets": [round(o, 3) for o in onsets.tolist()],
           "cuts": rows, "stats": stats}
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"BPM {bpm:.1f}  半拍 {30/bpm*1000:.0f}ms  起音 {len(onsets)} 个  拍点 {len(beats)} 个")
    for r in rows:
        print(f"  切点 {r['cut']:7.2f}  字头 {r['onset']:7.3f}({r['onset_diff_ms']:+5}ms)  "
              f"最近拍 {r['beat']:7.3f}")
    if stats:
        print(f"  字头偏差 中位 {stats['onset_median_ms']:.0f}ms / 最大 {stats['onset_max_ms']:.0f}ms")
        print(f"  若改贴网格 中位 {stats['grid_median_ms']:.0f}ms / 最大 {stats['grid_max_ms']:.0f}ms（同基准）")
    print("saved", a.json)


if __name__ == "__main__":
    main()
