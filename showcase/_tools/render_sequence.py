#!/usr/bin/env python3
"""案例②的分镜条（中英双语，两份 README 共用）。

四格全部取自成品片子本身，就是这三句歌词底下的四刀：
刀 13（转眼间，台阶与缓坡）→ 刀 14（一切都已改变，坡道加了扶手）
→ 刀 15（新的起点，司机拉出蓝色踏板）→ 刀 16（新的起点，从火车上下来）。

用法:
    python render_sequence.py <帧目录> [输出.png]

帧目录里放 f1..f4.png（960px 宽即可）。
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 600
BG = (14, 17, 22)
GREY, DIM, WHITE, ORANGE = (150, 160, 175), (122, 132, 148), (226, 232, 240), (255, 200, 90)
SAND = (196, 158, 96)

FRAMES = [
    ("f1", "刀 13「转眼间」", "台阶与缓坡，没有扶手", "shot 13 · 「in a blink」", "steps beside a ramp, no handrails", "街角"),
    ("f2", "刀 14「一切都已改变」", "坡道上加装了扶手", "shot 14 · 「all has changed」", "the ramp now carries handrails", "街边坡道"),
    ("f3", "刀 15「新的起点」", "司机把蓝色踏板拉出来", "shot 15 · 「a new start」", "the driver pulls the ramp out", "车旁"),
    ("f4", "刀 16「新的起点」", "从火车上下来，站台在眼前", "shot 16 · 「a new start」", "off the train, the platform ahead", "站台"),
]


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


im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
text = lambda xy, s, size, fill, bold=False, anchor=None: d.text(
    xy, s, font=font(size, bold), fill=fill, anchor=anchor)

# 标题
text((96, 22), "四刀，一条越来越顺的路", 28, WHITE, True)
text((96, 58), "Four cuts, one smoother road", 17, GREY)
text((96, 88), "《骄傲的少年》「转眼间 / 一切都已改变 / 新的起点」这三句底下就是四刀，按片子的顺序：台阶与缓坡 → 坡道加扶手 → 司机拉出踏板 → 从火车上下来。", 13, GREY)
text((96, 106), "「新的起点」占了最后两刀：一前一后，先是车，再是站台。", 13, GREY)
text((96, 124), "In 《骄傲的少年》, these three lines sit on four cuts, in film order: steps beside a ramp → the ramp gaining handrails → the driver pulling the ramp out → off the train.", 11, DIM)

# 四格
fw = 328
fh = int(fw * 9 / 16)
x0, y0, gap = 96, 152, 16
for i, (key, cn1, cn2, en1, en2, note) in enumerate(FRAMES):
    x = x0 + i * (fw + gap)
    p = os.path.join(sys.argv[1], key + ".png")
    if os.path.exists(p):
        img = Image.open(p).convert("RGB").resize((fw, fh))
        im.paste(img, (x, y0))
        d.rectangle([x, y0, x + fw - 1, y0 + fh - 1], outline=(52, 58, 68))
    else:
        d.rectangle([x, y0, x + fw, y0 + fh], outline=(60, 66, 76))
        text((x + fw // 2, y0 + fh // 2), key, 14, DIM, anchor="mm")
    size1 = 12 if font(12).getbbox(cn1)[2] <= fw else 11
    text((x, y0 + fh + 10), cn1, size1, WHITE)
    text((x, y0 + fh + 28), cn2, 12, GREY)
    text((x, y0 + fh + 48), en1, 10, DIM)
    text((x, y0 + fh + 63), en2, 10, DIM)
    text((x, y0 + fh + 80), note, 10, SAND)

# 结论
by = y0 + fh + 116
d.line([(96, by), (1504, by)], fill=(44, 50, 60))
text((96, by + 14), "转折成立的原因：四刀是同一件事的四个阶段，每一刀都有实物可指——台阶 → 坡道 → 坡道加扶手 → 车上的坡道。", 14, ORANGE)
text((96, by + 36), "Why the turn works: four stages of one thing, each with an object you can point at — steps, a ramp, a ramp with handrails, a ramp that rolls out of a car.", 12, SAND)
text((96, by + 60), "第 15 刀是一个连续的长镜头：从车门打开、司机弯腰拉踏板开始，到踏板铺平结束；第 16 刀接着换到站台。", 12, GREY)
text((96, by + 78), "Shot 15 is one continuous take, from the door opening to the ramp flat on the ground; shot 16 then cuts to the platform.", 11, DIM)

# 页脚
text((96, H - 30), "四格均取自成片（46.2 s / 49.0 s / 53.0 s / 55.2 s）；与 cut-proof.png 同一套视觉。", 10, DIM)
text((96, H - 16), "All four frames are taken from the film itself. Same visual language as cut-proof.png.", 10, DIM)

out = sys.argv[2] if len(sys.argv) > 2 else "sequence.png"
im.save(out)
print("saved", out, im.size)
