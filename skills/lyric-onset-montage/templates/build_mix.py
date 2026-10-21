# -*- coding: utf-8 -*-
"""歌词混剪构建模板：分镜 → 切片(垫底模糊) → 拼接 → 合曲。
改 SHOTS 就能用；切点=歌词字头，时长由相邻字头差反推。
"""
import os, subprocess, sys

FF = os.environ.get("FFMPEG", "ffmpeg")
FP = os.environ.get("FFPROBE", "ffprobe")
BASE = os.environ.get("WORK", "work")          # 项目工作区（切片、日志都放这）
SRC = os.environ.get("SRC", "source")          # 源素材目录
STAGE = os.path.join(BASE, "src")
CUTS = os.path.join(BASE, "cuts")
MUSIC = os.environ.get("MUSIC", "song.mp3")
OUT = os.environ.get("OUT", "out.mp4")
LOG = os.path.join(BASE, "build.log")
TOTAL = 98.0          # 成片总长（= 最后一个字头到结尾）

# (源文件, 入点秒, 时长秒, 说明)  —— 每半句一镜
SHOTS = [
    ("a.mp4", 100, 6.10, "0.00 前奏"),
    ("b.mp4", 6, 5.70, "6.10 前奏"),
    ("c.mp4", 2, 4.20, "11.80 我在清晨的路上"),
    # ...
]

PAD = ("[0:v]split=2[bg][fg];"
       "[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
       "gblur=sigma=55,eq=brightness=-0.28:saturation=0.85[bgo];"
       "[fg]scale=1920:1080:force_original_aspect_ratio=decrease[sfg];"
       "[bgo][sfg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v]")


def log(m):
    open(LOG, "a", encoding="utf-8").write(m + "\n")
    print(m, flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log("!! " + " ".join(map(str, cmd))[:300])
        log("!! " + (r.stderr or "")[-600:])
    return r.returncode


os.makedirs(CUTS, exist_ok=True)
open(LOG, "w", encoding="utf-8").close()

for i, (name, ss, dur, note) in enumerate(SHOTS):
    out = f"{CUTS}/c{i:02d}.mp4"
    if os.path.exists(out) and os.path.getsize(out) > 10000:   # 断点续跑
        log(f"[{i+1:02d}] 已就绪 {note}")
        continue
    p = os.path.join(STAGE, name)
    if not os.path.exists(p):
        p = os.path.join(SRC, name)
    fr = max(1, round(dur * 30))        # 帧精确：-t 会取整到帧，多刀累计会飘
    log(f"[{i+1:02d}] {note} @{ss}s {dur}s = {fr}帧")
    if run([FF, "-y", "-v", "error", "-ss", str(ss), "-i", p, "-frames:v", str(fr),
            "-filter_complex", PAD, "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p", out]) != 0:
        sys.exit(1)

lst = BASE + "/concat.txt"
with open(lst, "w", encoding="utf-8") as f:
    for i in range(len(SHOTS)):
        f.write(f"file 'cuts/c{i:02d}.mp4'\n")
VO = BASE + "/video_only.mp4"
if run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", VO]) != 0:
    sys.exit(1)

# 帧数自检：应等于 round(TOTAL*30)。不等 → 先查首刀有没有从 0 秒铺满，再查封片是否丢帧
probe = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_frames", "-of", "default=nw=1:nk=1", VO],
                       capture_output=True, text=True)
got, want = probe.stdout.strip(), str(round(TOTAL * 30))
if got != want:
    log(f"!! 帧数不符：实际 {got} / 预期 {want}")

# 淡出在成品阶段加，不烘进切片（穿插版要复用这些切片）
if run([FF, "-y", "-v", "error", "-i", VO, "-i", MUSIC,
        "-map", "0:v", "-map", "1:a",
        "-vf", "fade=t=out:st=%.1f:d=2.5" % (TOTAL - 2.5),
        "-af", "afade=t=in:st=0:d=0.5,afade=t=out:st=%.1f:d=2.5" % (TOTAL - 2.5),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k", "-t", str(TOTAL), OUT]) != 0:
    sys.exit(1)
log("完成: " + OUT)

# 要把这段成片当穿插版的“混剪部分”复用前，先量真实切点（30fps 取整，标称时间会差 1–3 帧）：
#   ffmpeg -i VO -vf "select='gt(scene,0.25)',showinfo" -f null - 2>&1 | grep -o 'pts_time:[0-9.]*'
# 规则：从切点后 1–2 帧进，结束停在下一刀前 1 帧；否则会把上一个镜头的残帧带出去（只闪 1 帧，但很难看）。
