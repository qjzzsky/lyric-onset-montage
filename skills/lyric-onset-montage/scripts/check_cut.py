# -*- coding: utf-8 -*-
"""check_cut.py —— 刀口体检：A/B 统计 + 帧数 + 末段电平 + 每刀首帧拼图

用法：
  python check_cut.py --video 成片.mp4 --table 镜头表.md --expect-frames 3472 --sheet cuts.jpg

口径（与 SKILL.md「怎么证明切得准」一致）：
  A = 切点 − 字头（刀准不准）
  B = 最近网格线 − 字头（按拍切会差多少）
  · 时间基准统一用「成片时间」
  · B 用「字头」找最近网格，绝不用切点（循环论证）
  · 相位拟合只用 40–160Hz 低频包络
  · 一句拆两刀时，第二刀（歌词与上一行相同）不计入 A
脚本红了必须停：任何一项 ✗ 都不要交付。
"""
import argparse, json, math, os, re, subprocess, sys, wave

import numpy as np
from scipy.signal import butter, sosfilt, find_peaks

SR = 22050
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".m4v")


# ───────────────────────── 基础工具 ─────────────────────────
def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe(video):
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries", "stream=nb_read_frames,r_frame_rate",
            "-show_entries", "format=duration", "-of", "json", video])
    if r.returncode != 0:
        sys.exit("ffprobe 失败：" + r.stderr[-400:])
    j = json.loads(r.stdout)
    st = j["streams"][0]
    num, den = (st.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    return {"frames": int(st.get("nb_read_frames") or 0),
            "fps": fps,
            "duration": float(j["format"]["duration"])}


def load_audio(video, tmpdir):
    wav = os.path.join(tmpdir, "check_audio.wav")
    r = sh(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-map", "0:a:0",
            "-ac", "1", "-ar", str(SR), wav])
    if r.returncode != 0 or not os.path.exists(wav):
        sys.exit("抽音频失败（有封面图流时要 -vn -map 0:a:0）：" + r.stderr[-300:])
    with wave.open(wav) as w:
        sig = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return sig


def bandpass(x, lo, hi, sr=SR, order=4):
    sos = butter(order, [lo / (sr / 2), hi / (sr / 2)], btype="band", output="sos")
    return sosfilt(sos, x)


def rms_env(x, hop=220, win=551):
    """10ms 帧 / 25ms 窗"""
    n = 1 + max(0, (len(x) - win)) // hop
    if n <= 0:
        return np.array([]), np.array([])
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    e = np.sqrt((x[idx] ** 2).mean(axis=1))
    return e, np.arange(n) * hop / SR


# ───────────────────────── 字头检测 ─────────────────────────
def detect_onsets(sig):
    """人声频段 300–3000Hz 的 RMS 上升起点（不是峰值）"""
    band = bandpass(sig, 300, 3000)
    env, t = rms_env(band)
    if len(env) < 10:
        return np.array([])
    d = np.diff(env)
    thr = max(d.std() * 1.2, 1e-4)
    peaks, _ = find_peaks(d, height=thr, distance=int(0.15 * SR / 220))
    # 上升起点：峰值前 0.12s 内第一个超过峰值 25% 的位置
    out = []
    for p in peaks:
        seg = env[max(0, p - int(0.12 * SR / 220)):p + 1]
        if len(seg) == 0:
            continue
        j = int(np.argmax(seg > seg[-1] * 0.25))
        out.append(t[max(0, p - int(0.12 * SR / 220)) + j])
    return np.array(sorted(out))


def detect_onsets_flux(sig):
    """对照口径：谱通量峰值（落在元音上，通常比 RMS 上升起点晚 50–150ms）"""
    hop, win = 128, 1024
    n = 1 + max(0, (len(sig) - win)) // hop
    if n <= 0:
        return np.array([])
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    S = np.abs(np.fft.rfft(sig[idx] * np.hanning(win), axis=1))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    flux /= (flux.max() + 1e-9)
    t = np.arange(len(flux)) * hop / SR + win / 2 / SR
    peaks, _ = find_peaks(flux, height=0.12, distance=int(0.15 * SR / hop))
    return t[peaks]


# ───────────────────────── 拍网格（低频） ─────────────────────────
def fit_grid(sig, lo=60, hi=120):
    """测速 + 相位，两步走（两个八度坑都在这）

    ① 测速：用**全带谱通量**的自相关，只在 60–120 BPM 里取峰，再做抛物线细化。
       低频 40–160Hz 的包络跟着贝斯走，会把 84.5 量成 96 或 167（实测踩过）。
    ② 相位：只用**低频包络**扫相位。测速和相位用不同频带，不矛盾——
       低频给「哪一下」，全带给「多久一下」。
    """
    hop, win = 128, 1024
    n = 1 + max(0, (len(sig) - win)) // hop
    if n <= 100:
        return None
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    S = np.abs(np.fft.rfft(sig[idx] * np.hanning(win), axis=1))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    flux = flux - flux.mean()
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    ac /= (ac[0] + 1e-12)
    fps = SR / hop
    lags = np.arange(len(ac)) / fps
    band = (lags > 60.0 / hi) & (lags < 60.0 / lo)
    if not band.any():
        return None
    k = int(np.argmax(np.where(band, ac, -9)))
    # 抛物线细化
    lag = lags[k]
    if 0 < k < len(ac) - 1:
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
        den = y0 - 2 * y1 + y2
        if abs(den) > 1e-9:
            lag += 0.5 * (y0 - y2) / den / fps
    bpm = 60.0 / lag

    # 相位：低频包络
    low = bandpass(sig, 40, 160)
    env, t = rms_env(low)
    env = env / (env.max() + 1e-12)
    period = 60.0 / bpm
    best = (0.0, -1.0)
    for ph in np.arange(0, period, 0.005):
        gi = (np.arange(ph, t[-1], period) * fps).astype(int)
        gi = gi[(gi >= 0) & (gi < len(env))]
        if len(gi) == 0:
            continue
        sc = float(env[gi].mean())
        if sc > best[1]:
            best = (ph, sc)
    return {"bpm": bpm, "period": period, "phase": best[0], "ac": float(ac[k]),
            "grid": np.arange(best[0], t[-1], period)}


# ───────────────────────── 镜头表 ─────────────────────────
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def parse_table(path):
    """读 markdown 镜头表：| # | 切点 | 时长 | 歌词 | … |

    「（前奏，无词）」「（间奏，无词）」不是字头刀，标 skip；
    歌词与上一行相同 = 一句拆两刀的第二刀（句内气口），标 second。
    """
    rows, lyric_seen = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            if not cells[0].isdigit():
                continue
            m = NUM.search(cells[1])
            if not m:
                continue
            cut = float(m.group())
            lyric = cells[3]
            skip = (not lyric) or lyric.startswith("（") or "无词" in lyric
            second = (not skip) and lyric == lyric_seen
            if not skip and lyric != lyric_seen:
                lyric_seen = lyric
            rows.append({"i": int(cells[0]), "cut": cut, "lyric": lyric,
                         "skip": skip, "second": bool(second)})
    return rows


# ───────────────────────── 首帧拼图 ─────────────────────────
def first_frames(video, cuts, out, cols=6, fps=30):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    try:
        from matplotlib import font_manager
        if os.path.exists("C:/Windows/Fonts/msyh.ttc"):
            font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    except Exception:
        pass
    tmp = os.path.splitext(out)[0] + "_tmp"
    os.makedirs(tmp, exist_ok=True)
    paths = []
    for k, c in enumerate(cuts):
        p = os.path.join(tmp, f"{k:03d}.jpg")
        # 帧号定位，不用 -ss（会取整到帧）
        n = int(round(c * fps)) + 1
        r = sh(["ffmpeg", "-y", "-v", "error", "-i", video,
                "-vf", f"select='eq(n\\,{n})',scale=320:-1", "-frames:v", "1", p])
        if not os.path.exists(p):
            r = sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{c:.3f}", "-i", video,
                    "-frames:v", "1", "-vf", "scale=320:-1", p])
        paths.append(p if os.path.exists(p) else None)

    rows = math.ceil(len(cuts) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.0, rows * 2.1), dpi=100)
    axes = np.atleast_2d(axes)
    for k in range(rows * cols):
        ax = axes[k // cols][k % cols]
        ax.axis("off")
        if k < len(cuts) and paths[k]:
            ax.imshow(plt.imread(paths[k]))
            ax.set_title(f"#{k + 1:02d}  {cuts[k]:.2f}s", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)
    for p in paths:
        if p and os.path.exists(p):
            os.remove(p)
    try:
        os.rmdir(tmp)
    except OSError:
        pass


# ───────────────────────── 主流程 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--table", required=True, help="镜头表 md（含 切点 / 歌词 两列）")
    ap.add_argument("--expect-frames", type=int, default=0)
    ap.add_argument("--sheet", default="", help="每刀首帧拼图输出路径")
    ap.add_argument("--bpm", type=float, default=0, help="覆盖自动测速")
    ap.add_argument("--onset-tol", type=float, default=0.6)
    ap.add_argument("--json", default="", help="把结果写成 JSON")
    a = ap.parse_args()

    info = probe(a.video)
    rows = parse_table(a.table)
    if not rows:
        sys.exit("镜头表没解析出切点，检查表格列顺序（# / 切点 / 时长 / 歌词）")

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sig = load_audio(a.video, td)
    onsets = detect_onsets(sig)
    onsets_flux = detect_onsets_flux(sig)
    grid = fit_grid(sig) if not a.bpm else None
    if a.bpm:
        period = 60.0 / a.bpm
        grid = {"bpm": a.bpm, "period": period,
                "grid": np.arange(0.0, len(sig) / SR, period)}

    # A：切点 − 字头（只算真字头刀；前奏/间奏与句内第二刀不计）
    A, A_flux, used = [], [], []
    for r in rows:
        if r["skip"] or r["second"]:
            continue
        near = onsets[np.abs(onsets - r["cut"]) <= a.onset_tol] if len(onsets) else []
        if len(near) == 0:
            continue
        on = float(near[np.argmin(np.abs(near - r["cut"]))])
        nf = onsets_flux[np.abs(onsets_flux - r["cut"]) <= a.onset_tol] if len(onsets_flux) else []
        onf = float(nf[np.argmin(np.abs(nf - r["cut"]))]) if len(nf) else float("nan")
        A.append((r["cut"] - on) * 1000.0)
        if not math.isnan(onf):
            A_flux.append((r["cut"] - onf) * 1000.0)
        used.append({"i": r["i"], "cut": r["cut"], "onset": round(on, 3),
                     "onset_flux": None if math.isnan(onf) else round(onf, 3),
                     "A_ms": round((r["cut"] - on) * 1000.0, 1),
                     "A_flux_ms": None if math.isnan(onf) else round((r["cut"] - onf) * 1000.0, 1),
                     "lyric": r["lyric"]})
    # B：最近网格 − 字头
    B = []
    if grid is not None and used:
        g = grid["grid"]
        for u in used:
            nb = float(g[np.argmin(np.abs(g - u["onset"]))])
            B.append((nb - u["onset"]) * 1000.0)
            u["grid"] = round(nb, 3)
            u["B_ms"] = round((nb - u["onset"]) * 1000.0, 1)

    # 末段电平
    tail = sig[-int(0.1 * SR):]
    tail_db = 20 * math.log10(float(np.sqrt((tail ** 2).mean())) + 1e-9)

    # 报告
    print("=" * 58)
    print(f"成片：{os.path.basename(a.video)}")
    print(f"时长 {info['duration']:.3f}s ｜ 帧数 {info['frames']} ｜ {info['fps']:.3f}fps")
    if a.expect_frames:
        d = info["frames"] - a.expect_frames
        flag = "✓" if d == 0 else ("✗ 少帧" if d < 0 else "✗ 多帧")
        print(f"帧数核对：期望 {a.expect_frames} 实测 {info['frames']} 差 {d:+d}  {flag}")
    else:
        print("帧数核对：未给 --expect-frames（建议给）")
    print(f"末尾 0.1s 电平：{tail_db:.1f} dBFS  "
          f"{'✓ (< -45dB)' if tail_db < -45 else '✗ 仍能听见'}")
    print(f"字头刀数 n={len(A)} ｜ 检出起音点 {len(onsets)} 个")
    if A:
        arr = np.array(A)
        print(f"A 切点−字头（RMS 上升起点）：中位 {np.median(arr):+.0f}ms ｜ 绝对中位 "
              f"{np.median(np.abs(arr)):.0f}ms ｜ 最大 {np.abs(arr).max():.0f}ms")
    if A_flux:
        arr2 = np.array(A_flux)
        print(f"A 切点−字头（谱通量峰，对照）：中位 {np.median(arr2):+.0f}ms ｜ 绝对中位 "
              f"{np.median(np.abs(arr2)):.0f}ms ｜ 最大 {np.abs(arr2).max():.0f}ms")
    if B:
        arr = np.array(B)
        print(f"B 网格−字头 ：中位 {np.median(arr):+.0f}ms ｜ 绝对中位 {np.median(np.abs(arr)):.0f}ms "
              f"｜ 最大 {np.abs(arr).max():.0f}ms")
    if grid is not None:
        print(f"曲速 {grid['bpm']:.1f} BPM ｜ 格距 {grid['period']:.3f}s ｜ "
              f"半拍 {grid['period'] * 500:.0f}ms ｜ 通量自相关 {grid.get('ac', 0):.2f}")
        if B and np.median(np.abs(B)) < grid["period"] * 1000 / 10:
            print("✗ 自检：median|B| < 半拍/5，几乎一定算错（网格被人声吸走？）")
    if len(A) >= 5:
        print("\n逐刀：")
        for u in used:
            print(f"  #{u['i']:02d}  切点 {u['cut']:7.3f}  字头 {u['onset']:7.3f}  "
                  f"网格 {u.get('grid', float('nan')):7.3f}  A {u['A_ms']:+6.0f}ms  "
                  f"B {u.get('B_ms', float('nan')):+6.0f}ms  {u['lyric'][:14]}")

    if a.sheet:
        first_frames(a.video, [r["cut"] for r in rows], a.sheet, fps=info["fps"])
        print(f"\n首帧拼图：{a.sheet}")

    if a.json:
        json.dump({"video": a.video, "frames": info["frames"], "fps": info["fps"],
                   "duration": info["duration"], "tail_db": tail_db,
                   "n": len(A), "A_ms": A, "B_ms": B,
                   "bpm": (grid or {}).get("bpm"), "rows": used},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"JSON：{a.json}")


if __name__ == "__main__":
    main()
