#!/usr/bin/env python3
"""三类证据图的图例（中英双语，两份 README 共用一张）。

三格缩略图都取自真实案例文件：
① showcase/骄傲的少年-115s/cut-proof.png
② showcase/骄傲的少年-115s/分镜首帧.jpg
③ showcase/骄傲的少年-115s/cut-frame.png

用法:
    python render_legend.py <showcase 根目录> [输出.png]
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 730
BG, PANEL = (14, 17, 22), (22, 26, 33)
GREY, DIM, WHITE, SAND = (150, 160, 175), (122, 132, 148), (226, 232, 240), (196, 158, 96)
RED, ORANGE = (255, 80, 80), (255, 200, 90)

PANELS = [
    ("骄傲的少年-115s/cut-proof.png", "① 双轨刀口图", "cut timing",
     "浅蓝＝波形，灰竖线＝节拍网格，红线＝切点（按实测字头落刀）。",
     "答：整片的切点是不是都落在字头上。交付前体检；解释 A/B 两个数。",
     "The cut is on the word: waveform, beat grid, measured onsets — checked before delivery."),
    ("骄傲的少年-115s/分镜首帧.jpg", "② 首帧拼图", "shot choice",
     "一格一刀，编号与镜头表同号；扫空镜、压人头、相邻两刀同素材同入点。",
     "答：每一刀的画面选得对不对。下刀前点号；返修后复核。",
     "One frame per cut, numbered like the shot table: is each shot the right choice."),
    ("骄傲的少年-115s/cut-frame.png", "③ 刀口帧对照", "does the cut change the shot",
     "左＝切点前 1 帧，右＝切点帧；内容相同＝同镜残留，整帧全黑＝黑场。",
     "答：这一刀是不是真的换了镜。单刀返修与换镜核对时用。",
     "Did this cut actually change the shot: the frame before vs the frame at the cut."),
]


def font(size, bold=False):
    for p in (os.path.join(os.environ.get("WINDIR", ""), "Fonts", "msyhbd.ttc" if bold else "msyh.ttc"),
              "/System/Library/Fonts/PingFang.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


root = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "legend.png"

im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
text = lambda xy, s, size, fill, bold=False, anchor=None: d.text(
    xy, s, font=font(size, bold), fill=fill, anchor=anchor)

text((96, 26), "三类证据，三个问题", 32, WHITE, True)
text((96, 68), "Three kinds of evidence, three different questions", 18, GREY)
text((96, 94), "切点准不准 · 素材选得对不对 · 是不是真换了镜——一张图答一个，互相替代不了。", 14, GREY)
text((96, 114), "Cut accuracy, shot choice, and whether the cut changed the shot: one figure per question, none of them a substitute for the others.", 12, DIM)

pw, ph = 456, 250
x0, y0, gap = 96, 196, 36
for i, (rel, cn, en, l1, l2, en2) in enumerate(PANELS):
    x = x0 + i * (pw + gap)
    d.rectangle([x - 10, y0 - 46, x + pw + 10, 616], fill=PANEL)
    text((x, y0 - 36), cn, 18, WHITE, True)
    text((x, y0 - 6), en, 10, DIM)
    p = os.path.join(root, rel)
    if os.path.exists(p):
        img = Image.open(p).convert("RGB")
        img.thumbnail((pw, ph))
        im.paste(img, (x + (pw - img.width) // 2, y0))
        d.rectangle([x, y0, x + pw - 1, y0 + ph - 1], outline=(52, 58, 68))
    else:
        d.rectangle([x, y0, x + pw, y0 + ph], outline=(60, 66, 76))
        text((x + pw // 2, y0 + ph // 2), "missing", 14, DIM, anchor="mm")
    ty = y0 + ph + 16
    for line, size, col in ((l1, 13, GREY), (l2, 13, ORANGE), (en2, 11, DIM)):
        # 简单折行：按像素宽度切
        words, cur = line.split(" "), ""
        while words:
            w = words[0]
            trial = (cur + " " + w).strip()
            if font(size).getbbox(trial)[2] > pw and cur:
                text((x, ty), cur, size, col)
                ty += size + 8
                cur = w
            else:
                cur = trial
            words.pop(0)
        if cur:
            text((x, ty), cur, size, col)
            ty += size + 10

text((96, 634), "三条通用规则：可复现（能指回帧号、数值、文件名）· 同号（图上编号＝镜头表编号）· 内部分工（尺子图只给自己核对，不进交付）",
     12, SAND)
text((96, 656), "Three rules: reproducible, same numbering as the shot table, and internal-only rulers kept out of the delivery.",
     11, DIM)
text((96, 684), "缩略图取自案例② 的真实文件；与 cut-proof.png、sequence.png 同一套视觉。",
     10, DIM)

im.save(out)
print("saved", out, im.size)
