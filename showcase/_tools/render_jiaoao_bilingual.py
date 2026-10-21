#!/usr/bin/env python3
"""重出案例②的刀口图（中英双语一张，两份 README 共用）。

左中右全是实测：波形来自交付成片音轨，红线是参考_字头与切点.csv 里的实测字头，
灰线是按 84.0 BPM 排的等间隔网格，相位取「最近网格线落在 82.61s」。

用法:
    python render_jiaoao_bilingual.py <成片.mp4> <参考_字头与切点.csv> [输出.png]

依赖: ffmpeg, numpy, scipy, Pillow
"""
import csv, os, subprocess, sys, tempfile, wave
import numpy as np
from scipy.signal import butter, sosfilt
from PIL import Image, ImageDraw, ImageFont

# ---- 取图常量（与案例②一致） ----
OFFSET = 2.38          # 成片 0s = 原曲 2.38s（自检报告记录）
WIN0, WIN1 = 78.0, 90.0
BPM = 84.0
T = 60.0 / BPM
GRID_AT = 82.606       # 距离「燃烧吧」82.26s 最近的网格线
W, H = 1600, 1040
X0, X1 = 96, 1568

BG    = (14, 17, 22)
WAVE  = (104, 148, 205)
GRIDC = (196, 206, 222)
RED   = (255, 80, 80)
GREY  = (150, 160, 175)
DIM   = (122, 132, 148)
ORANGE= (255, 200, 90)
WHITE = (226, 232, 240)


def font(size, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              "/System/Library/Fonts/PingFang.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def envelope(mp4, tmp):
    wav = os.path.join(tmp, "song.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vn", "-ac", "1",
                    "-ar", "48000", "-c:a", "pcm_s16le", wav], check=True)
    with wave.open(wav) as f:
        sr = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    sos = butter(4, [300, 3000], btype="band", fs=sr, output="sos")
    x = sosfilt(sos, x)
    hop = int(0.01 * sr)                      # 10ms RMS
    n = len(x) // hop
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return rms, 0.01


def main():
    mp4, csv_path = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "cut-proof.png"
    with tempfile.TemporaryDirectory() as tmp:
        rms, dt = envelope(mp4, tmp)

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    onsets = [(float(r["字头_原曲秒"]), r["歌词"]) for r in rows]
    onsets = [(t, s) for t, s in onsets if WIN0 <= t <= WIN1]

    scale = (X1 - X0) / (WIN1 - WIN0)          # px per second
    to_x = lambda t: X0 + (t - WIN0) * scale

    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    F = font

    def text(xy, s, size, fill, bold=False, anchor=None):
        d.text(xy, s, font=F(size, bold), fill=fill, anchor=anchor)

    # ---------- 标题 ----------
    text((96, 22), "字头对齐 vs 鼓点对齐", 30, WHITE, True)
    text((96, 62), "Lyric onsets vs. the beat grid", 19, GREY)
    text((96, 98), "前半首 20 句实测：中位 0.22s、四分位 0.19–0.32s（单句最大约 0.35s，约半拍 0.357s）；相位法不确定 R=0.04", 15, GREY)
    text((96, 121), "First 20 lines: median 0.22 s, quartiles 0.19–0.32 s (worst line ≈0.35 s ≈ half a beat); phase fit inconclusive, R=0.04", 12, DIM)
    text((96, 142), "音源《骄傲的少年》（演唱 南征北战NZBZ｜词 赵辰龙｜曲 汀洋）｜ 窗口 78–90s ｜ 曲速 84.0 BPM（网格相位已校正）｜ 半拍 0.357s ｜ 观测点：能量峰（比嘴唇字头晚 0.1–0.3s）", 14, GREY)
    text((96, 162), "Source 《骄傲的少年》 (NZBZ; lyrics 赵辰龙; music 汀洋) | window 78–90 s | tempo 84.0 BPM, grid phase corrected | half beat 0.357 s | peaks read 0.1–0.3 s after the lips", 12, DIM)

    # ---------- 两条轨 ----------
    tracks = [(226, 470), (544, 800)]
    win_lo, win_hi = int(WIN0 / dt), int(WIN1 / dt)
    peak = float(np.percentile(rms[win_lo:win_hi], 97)) or 1.0
    for (y0, y1) in tracks:
        mid, amp = (y0 + y1) // 2, (y1 - y0) // 2 - 4
        x = X0
        while x <= X1:
            t0 = (x - X0) / scale + WIN0
            i0 = int(t0 / dt)
            i1 = min(len(rms), i0 + max(1, int((1 / scale) / dt) + 1))
            v = float(rms[i0:i1].max()) if i1 > i0 else 0.0
            h = max(1, int(v / peak * amp))
            d.line([(x, mid - h), (x, mid + h)], fill=WAVE)
            x += 1

    # 网格：等间隔，相位由 GRID_AT 定，只画窗口内的线
    p = GRID_AT - round((GRID_AT - WIN0) / T + 0) * T
    k = int(np.ceil((WIN0 - p) / T))
    while True:
        g = p + k * T
        if g > WIN1:
            break
        if g >= WIN0:
            gx = to_x(g)
            d.line([(gx, tracks[0][0]), (gx, tracks[0][1])], fill=GRIDC)
            d.line([(gx, tracks[1][0]), (gx, tracks[1][1])], fill=GRIDC)
        k += 1

    # ---------- 红线 + 歌词 ----------
    gloss = {"是坚定的信念": "a firm belief", "燃烧吧": "burn!",
             "骄傲的热血": "pride's hot blood", "胜利的歌我要再唱一遍": "the victory song, sing it once more"}
    for t, s in onsets:
        gx = to_x(t)
        # 红线加一圈底色，避免被蓝色波形吃掉（1px 红线在密波形上看不见）
        d.line([(gx, tracks[0][0] - 8), (gx, tracks[1][1] + 8)], fill=BG, width=5)
        d.line([(gx, tracks[0][0] - 8), (gx, tracks[1][1] + 8)], fill=RED, width=2)
        text((gx, 808), s, 13, RED, anchor="ma")
        if s in gloss:
            text((gx, 826), gloss[s], 11, (170, 120, 120), anchor="ma")

    # ---------- 346ms 标注 ----------
    t_on = next(t for t, s in onsets if s == "燃烧吧")
    gx_on, gx_grid = to_x(t_on), to_x(GRID_AT)
    d.line([(gx_on, 576), (gx_grid, 576)], fill=WHITE)
    for gx in (gx_on, gx_grid):
        d.line([(gx, 566), (gx, 586)], fill=WHITE)
    bx0, bx1 = gx_on - 6, gx_grid + 6
    d.rectangle([bx0, 549, bx1, 573], fill=BG)
    text(((bx0 + bx1) / 2, 551), "346ms", 14, WHITE, anchor="ma")

    # ---------- 轨道说明（最后画，背板压住网格线和红线） ----------
    for yy, c1, c2 in ((186, "① 鼓点网格（84.0 BPM，等间隔）", "① Beat grid (84.0 BPM, evenly spaced)"),
                       (504, "② 实测起唱峰（能量法 300–3000Hz / 10ms RMS）", "② Measured onsets (300–3000 Hz energy, 10 ms RMS)")):
        for i, (s, size, col) in enumerate(((c1, 13, WAVE), (c2, 11, DIM))):
            ty = yy + (17 if i else 0)
            bb = F(size).getbbox(s)
            d.rectangle([93, ty + bb[1] - 3, 99 + bb[2] + 3, ty + bb[3] + 3], fill=BG)
            text((96, ty), s, size, col)

    # ---------- 结论 ----------
    text((96, 856), "最大一处：「燃烧吧」峰 82.26s，最近网格 82.61s，差 +346ms（示例，随相位浮动）", 15, ORANGE)
    text((96, 877), 'Largest gap: “燃烧吧” onset 82.26 s vs nearest grid line 82.61 s → +346 ms (one example; shifts with phase)', 12, (196, 158, 96))
    d.line([(96, 908), (132, 908)], fill=GRIDC)
    text((140, 900), "鼓点网格 / beat grid", 12, GREY)
    d.line([(330, 908), (366, 908)], fill=RED)
    text((374, 900), "实测能量峰 / measured onset", 12, GREY)

    text((96, 932), "为什么不用节拍：节拍只给出等间隔网格，不知道「哪个鼓点开始一句」；", 13, GREY)
    text((96, 951), "Why not cut to the beat: a tempo gives an evenly spaced grid, not which drum starts a line.", 12, DIM)
    text((96, 974), "中文歌的弱起句常抢在半拍前，按网格切就是 200–300ms 级误差。", 13, GREY)
    text((96, 993), "Chinese pop lines often start ahead of the half-beat; cutting on the grid costs 200–300 ms.", 12, DIM)

    text((96, 1014), "生成：DeepSeek Harness (DSH) ｜ 模型：DeepSeek V4.1", 11, DIM)
    text((560, 1014), "made with DeepSeek V4.1 on DeepSeek Harness (DSH)", 11, DIM)

    im.save(out)
    print("saved", out, im.size)


if __name__ == "__main__":
    main()
