#!/usr/bin/env python3
"""SRT（B 站 UP 主字幕）→ 切点候选表。

用法: python srt_to_cuts.py subs.srt > cuts.json

做四件事：
1. 判断字幕是**人工（UP 自制）还是自动（平台 AI）**：文件名带 `ai-zh` 的按自动处理，句界权重降为 `low`；输出 `sub_type` / `boundary_weight` 两个字段；
2. 括号条目不再一律删：≥1.0 秒的保留并标 `harmony: true`——它可能是和声/伴唱（与主唱重叠或独立成句），也可能是 UP 主注解，下刀前听一遍再定；
3. 短于 1.0 秒的条目并入上一句（碎刀的主要来源）；
4. 标出 >4.7 秒的长条（疑似字幕把两句并成一条，用字幕句界 + 能量起点定第二句首字）。

注意：输出的是「候选窗口」，不是字头。字幕对轴通常比演唱早或晚 0.1–0.3 秒，
下刀前还要用音频能量上升起点收口（见 references/lyric-timing.md）。
"""
import json
import os
import re
import sys

TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
ASIDE = re.compile(r"^[（(].*[）)]$")


def sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse(path):
    txt = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    rows = []
    for block in [b for b in txt.strip().split("\n\n") if b.strip()]:
        m = TS.search(block)
        if not m:
            continue
        g = m.groups()
        rows.append({
            "start": round(sec(*g[:4]), 2),
            "end": round(sec(*g[4:]), 2),
            "text": " ".join(block.splitlines()[2:]).strip(),
        })
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    base = os.path.basename(path).lower()
    auto = base.startswith("ai") or "ai-zh" in base
    clean = []
    for r in parse(sys.argv[1]):
        short = r["end"] - r["start"] < 1.0
        aside = bool(ASIDE.match(r["text"]))
        if short and clean:                  # 太短（含 0.6-0.9 秒的括号和声/注解）：并句
            clean[-1]["end"] = r["end"]
            continue
        if aside:                            # 可能是和声/伴唱，也可能是 UP 注解：保留待听
            r["harmony"] = True
            r["text"] = r["text"].strip("（）() ")
        clean.append(r)

    for i, r in enumerate(clean):
        r["dur"] = round(r["end"] - r["start"], 2)
        r["next_start"] = clean[i + 1]["start"] if i + 1 < len(clean) else None
        r["review"] = "长条，疑似两句并一条" if r["dur"] > 4.7 else ""

    out = {
        "source": base,
        "sub_type": "auto" if auto else "manual",
        "boundary_weight": "low" if auto else "high",
        "cues": clean,
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print(
        f"\n# {len(clean)} 条候选；中位 {sorted(x['dur'] for x in clean)[len(clean)//2]}s；"
        f"字幕类型 {'自动（句界只当粗窗口）' if auto else '人工（句界可直接用）'}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
