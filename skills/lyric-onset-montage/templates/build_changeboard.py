# -*- coding: utf-8 -*-
"""
build_changeboard.py — 从 镜头表.md 生成 改动台.html

用法：
    python build_changeboard.py 镜头表.md [--title "《歌名》混剪"] [--video 成片.mp4] [--lang zh|en] [-o 改动台.html]

规矩（与技能一致）：
- 列按表头名字定位（#/序号、切点、时长、歌词、素材、入点），不按列位置；表头中英文皆认。
- 成片自动挂同目录那一支（多个视频时用 --video 指定）：打开即播，刷新不断。
- 数据内嵌 JSON：不联网、不碰素材库。
- 点分镜从切点前 3 秒起播放（看清切入，类似弹幕定位）；列表头复选框勾上「循环播放」才循环。同句两刀的续刀行以 └ 开头（如 └的门）。
- 「时机不对」弹窗：循环看这一刀前后几秒，点「调整到这里」把目标切点记进提示词。
- 键盘：← → 快退/快进 2 秒、空格暂停（全局+弹窗通用；「我有别的想法」输入框聚焦时不启用）。按钮第一格「无需调整」是默认态；输入框未选「我有别的想法」时只读。
- 列表 LRC 式自动跟随：播放到哪刀，列表与右侧面板自动跟到哪刀（只在没点分镜时跟；点过行的预览/循环、弹窗打开、正在输入时不抢选中，选中刀的切点前 3 秒引导段里也不换）。
- 汇总按钮两态：无改动＝绿色「复制确认提示词」（确认无误、可直接生成）；有改动＝蓝色「复制改动提示词」。
- 页面只收集改动意见、不改片；输出的提示词贴回 AI 走「最小改动」流程。
- 双语界面：--lang 只定初始语言（跟使用者提示词的语言走）；右上角「中 / EN」开关随时切换，切换即时生效、提示词文案跟随界面语言，手动选择记在本地、刷新不丢（识别失效时的兜底）。
"""
import argparse
import json
import re
from pathlib import Path

COL_ALIASES = {
    "no": ("#", "序号", "刀号", "编号", "no", "shot"),
    "cut": ("切点", "cut"),
    "dur": ("时长", "duration", "dur"),
    "lyric": ("歌词", "lyrics", "lyric"),
    "mat": ("素材", "material", "mat"),
    "in": ("入点", "in-point", "in"),
    "mood": ("情绪", "mood"),
}

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def parse_shots(md_text):
    rows, colmap = [], None
    for raw in md_text.splitlines():
        line = raw.strip().strip("\r")
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # 表头分隔行
        if colmap is None:
            colmap = {}
            for i, name in enumerate(cells):
                key = name.strip().lower()
                for k, aliases in COL_ALIASES.items():
                    if k in colmap:
                        continue
                    if any(key == a or key.startswith(a) for a in aliases):
                        colmap[k] = i
            if "cut" not in colmap or "lyric" not in colmap:
                raise SystemExit("镜头表里找不到「切点」「歌词」列；表头：%s" % cells)
            continue

        def cell(key, default=""):
            i = colmap.get(key)
            return cells[i].strip() if i is not None and i < len(cells) else default

        m = re.search(r"-?[\d.]+", cell("cut"))
        if not m:
            continue
        cut = float(m.group())
        m2 = re.search(r"[\d.]+", cell("dur"))
        no_s = cell("no")
        rows.append({
            "no": int(no_s) if no_s.isdigit() else len(rows) + 1,
            "cut": cut,
            "dur": float(m2.group()) if m2 else None,
            "lyric": cell("lyric"),
            "mat": cell("mat"),
            "in": cell("in"),
            "mood": cell("mood"),
        })
    if not rows:
        raise SystemExit("没解析到任何分镜行")
    return rows


def detect_video(out_dir: Path, explicit, folder_name: str) -> str:
    if explicit:
        p = Path(explicit)
        if not p.exists() and not (out_dir / p.name).exists():
            raise SystemExit("--video 指定的文件不存在：%s" % explicit)
        return p.name
    vids = sorted(f for f in out_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS)
    if not vids:
        raise SystemExit("目录里没有视频文件（%s）：成片要和 改动台.html 放同一个目录" % out_dir)
    for pref in ("成片.mp4", folder_name + ".mp4"):
        if (out_dir / pref).exists():
            return pref
    if len(vids) == 1:
        return vids[0].name
    raise SystemExit("目录里有多个视频（%s）：用 --video 指定一个" % "、".join(v.name for v in vids))


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--blue:#1f6feb;--ink:#16283f;--muted:#5b6b80;--line:#d7e1ee;--bg:#f4f7fb;--card:#fff;
--ok:#24a148;--warn:#f0a202;--bad:#e2574c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:18px 20px 48px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px}
h1{font-size:20px;margin:0 0 2px}
h1 .sub{font-size:13px;color:var(--muted);font-weight:400;margin-left:8px}
.langsw{display:flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;flex:none}
.langsw button{border:0;border-radius:0;padding:4px 13px;font-size:12px;line-height:1.6;
color:var(--muted);background:var(--card)}
.langsw button:hover{color:var(--blue)}
.langsw button.on{background:var(--blue);color:#fff}
.status{font-size:13px;color:var(--muted);margin:2px 0 14px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:baseline}
.dot.ok{background:var(--ok)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--bad)}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:8px;padding:7px 14px;cursor:pointer}
button:hover{border-color:var(--blue);color:var(--blue)}
button.primary{background:var(--blue);border-color:var(--blue);color:#fff}
button.primary:hover{opacity:.92;color:#fff}
button.ok{background:var(--ok);border-color:var(--ok);color:#fff}
button.ok:hover{opacity:.92;color:#fff}
button.on{background:#e8f0fe;border-color:var(--blue);color:var(--blue)}
.video-box{background:#0d1520;border-radius:10px;overflow:hidden;margin:0 0 14px}
video{width:100%;max-height:52vh;display:block;background:#0d1520}
.hint{font-size:12px;color:var(--muted);margin:0 0 14px}
.grid{display:grid;grid-template-columns:1fr 340px;gap:14px;align-items:start;position:relative}
@media(max-width:860px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.card h2{font-size:13px;margin:0;padding:10px 14px;border-bottom:1px solid var(--line);
color:var(--muted);font-weight:600;letter-spacing:.02em;display:flex;align-items:center;gap:8px}
.redhint{color:var(--bad);font-weight:700}
#note.ro{background:#eef2f8;color:var(--muted)}
.h2fill{flex:1}
.loopbox{display:flex;align-items:center;gap:5px;font-weight:400;cursor:pointer;white-space:nowrap}
.loopbox input{accent-color:var(--blue);width:15px;height:15px;cursor:pointer}
.ovl{position:absolute;inset:0;background:rgba(22,40,63,.45);border-radius:10px;z-index:50;display:flex;align-items:center;justify-content:center}
.ovl .modal{background:var(--card);border-radius:12px;padding:18px 20px;width:min(560px,92%);box-shadow:0 12px 40px rgba(13,21,32,.35)}
.ovl h3{margin:0 0 8px;font-size:15px}
.ovl p{margin:0 0 12px;font-size:13px;line-height:1.8;color:var(--muted)}
.ovl .now{font-variant-numeric:tabular-nums;color:var(--ink);font-weight:600}
.rows{max-height:52vh;overflow:auto}
.row{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--line);
cursor:pointer;font-size:13px}
.row:hover{background:#f2f7ff}
.row.grp-a{box-shadow:inset 2px 0 0 var(--blue)}
.row.grp-b{box-shadow:inset 2px 0 0 #a8c6f5;padding-left:30px}
.row.sel{background:#e8f0fe;box-shadow:inset 3px 0 0 var(--blue)}
.row .no{width:38px;color:var(--muted);flex:none}
.row .t{width:86px;color:var(--muted);flex:none;font-variant-numeric:tabular-nums}
.row .lyric{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .mat{width:150px;color:var(--muted);flex:none;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;font-size:12px}
.row .mk{flex:none;font-size:12px;color:var(--bad)}
.tag{display:inline-block;font-size:11px;line-height:1.7;padding:0 6px;border-radius:6px;
background:#e8f0fe;color:var(--blue);margin-left:6px;vertical-align:middle}
.panel{padding:14px}
.panel .who{font-size:13px;margin:0 0 10px;line-height:1.6}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.btns button{flex:1 1 44%;padding:8px 6px}
textarea{width:100%;min-height:76px;resize:vertical;border:1px solid var(--line);border-radius:8px;
padding:8px 10px;font:inherit;font-size:13px;color:var(--ink)}
.tip{font-size:12px;color:var(--muted);margin:8px 0 0}
.foot{margin-top:14px}
.prompt{width:100%;min-height:110px;margin-top:10px;background:var(--card)}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <h1>__TITLE__<span class="sub" id="tSub"></span></h1>
    <div class="langsw" id="langSw"><button data-l="zh">中</button><button data-l="en">EN</button></div>
  </div>
  <div class="status"><span class="dot warn" id="vDot"></span><span id="vState"></span>
    <span id="loopState"></span></div>
  <p class="hint" id="hintP"></p>
  <div class="video-box"><video id="video" controls preload="metadata"></video></div>
  <div class="grid">
    <div class="ovl" id="ovl" style="display:none">
      <div class="modal">
        <h3 id="ovlTitle"></h3>
        <p><span id="ovlDesc"></span><span class="redhint" id="ovlRed"></span><span id="ovlKeys"></span><br>
        <span id="ovlNowLbl"></span><span class="now" id="ovlNow">0.00</span><span id="ovlOldLbl"></span><span class="now" id="ovlOld">0.00</span>s</p>
        <div class="btns">
          <button class="primary" id="ovlSet"></button>
          <button id="ovlClear" style="display:none"></button>
          <button id="ovlCancel"></button>
        </div>
      </div>
    </div>
    <div class="card">
      <h2><span id="shotsTitle"></span><span class="redhint" id="shotsRed"></span><span class="h2fill"></span><label class="loopbox"><input type="checkbox" id="loopChk"> <span id="loopLbl"></span></label></h2>
      <div class="rows" id="rows"></div>
    </div>
    <div>
      <div class="card">
        <h2><span id="fbTitle"></span></h2>
        <div class="panel" id="panel">
          <p class="who" id="who"></p>
          <div class="btns" id="btns" style="display:none">
            <button data-k="none" class="on"></button>
            <button data-k="timing"></button>
            <button data-k="swap"></button>
            <button data-k="other"></button>
          </div>
          <textarea id="note" style="display:none"></textarea>
          <p class="tip" id="tip" style="display:none"></p>
        </div>
      </div>
      <div class="card foot">
        <h2><span id="sumTitle"></span></h2>
        <div class="panel">
          <button class="ok" id="copyBtn"></button>
          <span class="status" style="margin:0 0 0 8px" id="copyState"></span>
          <textarea class="prompt" id="prompt" readonly></textarea>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
const SHOTS = __SHOTS__;
const TITLE = __TITLEJS__;
const VIDEO_SRC = __VIDEOJSON__;
const OUTNAME = "__OUTNAME__";
const DEF_LANG = "__LANG__";
const LEAD = 3.0; // 切点前几秒起播（弹幕定位式）
const TAIL = 3.0; // 时机调整循环里，这一刀后再播几秒
let sel = -1, looping = false, loopStart = 0, loopEnd = 0, videoState = "loading";
const marks = {};
const $ = id => document.getElementById(id);
const video = $("video");
const fmt = t => (Math.round(t * 100) / 100).toFixed(2);

// ── 双语文案：zh / en 各一套；右上角开关切换，提示词文案跟随界面语言 ──
const I18N = {
  zh: {
    sub: "改动台",
    loading: "正在载入成片…",
    hint: "成片自动带同文件夹那一支，打开即播。点分镜 = 从切点前 3 秒起播放看清切入（类似弹幕定位）；蓝竖条 + └ = 同一句歌词断成两刀，└ 后写这一刀唱的部分。勾上「循环播放」后点分镜才循环这一段。觉得切入时机不对 → 点「时机不对」，循环看着点「调整到这里」精确定点。在下面选改动，最后复制提示词贴回 AI。全程本地，不联网。",
    shotsTitle: "分镜 · ",
    shotsRed: "点击分镜后，视频将从分镜的前三秒处开始播放，以便分辨。可以通过键盘的左和右键，快速对播放进度进行调整。",
    loop: "循环播放",
    fbTitle: "改动意见",
    sumTitle: "汇总",
    whoEmpty: "还没选分镜。点左边任意一行开始。",
    kNone: "无需调整", kTiming: "时机不对", kSwap: "换素材", kOther: "我有别的想法",
    markOther: "其他",
    noLyricRow: "（无词）", noLyric: "无词",
    q1: "「", q2: "」",
    inAt: v => " @入点 " + v,
    notePh: "补充说明，可不填。例：一点点 / 换个城市空镜",
    copyConfirm: "复制确认提示词", copyChange: "复制改动提示词",
    planReady: "无需调整，方案就绪",
    promptPh: "改动意见汇总后会显示在这里",
    copied: "已复制到剪贴板，去 AI 对话里粘贴",
    clipBlocked: "剪贴板受限，已选中文本，Ctrl+C 复制",
    ovlTitleDef: "调整切点",
    ovlDesc: "视频在循环：切点前 3 秒 → 这一刀后 3 秒。",
    ovlRed: "看到该切的位置，点「调整到这里」",
    ovlKeys: "（键盘 ← → 快退/快进 2 秒，空格暂停）。",
    ovlNowLbl: "当前 ", ovlOldLbl: "s ｜ 现在的切点 ",
    ovlSet: "调整到这里", ovlClear: "清除这刀的时机意见", ovlCancel: "取消",
    loaded: (v, d) => `成片已载入：${v}（${d}s）`,
    missing: v => `成片没找到：${OUTNAME} 要和成片放在同一个文件夹（现在找的是 ${v}），放好后刷新`,
    tagPair: first => `同句${first ? "前刀" : "后刀"}`,
    tagPairP: first => `（同句${first ? "前刀" : "后刀"}）`,
    loopState: (no, a, b, lead) => ` ｜ 循环中：#${no}（${a}–${b}s${lead ? "，切点前 3 秒起" : ""}）`,
    marked: n => `已标记 ${n} 刀`,
    ovlTitle: (no, cut) => `第 ${no} 刀 ${cut}s · 调整切点`,
    txtTiming: (t, d) => `时机不对，切点调整到 ${t}s（${d < 0 ? "提前" : "推迟"} ${fmt(Math.abs(d))}s）`,
    txtOther: note => `其他：${note || "（没写内容，待补）"}`,
    noteSuffix: note => `；备注：${note}`,
    promptLine: (no, cut, quoted, gtag, txt) => `第 ${no} 刀 ${cut}s${quoted}${gtag}——${txt}`,
    promptHead: () => `${TITLE} 改动意见（改动台汇总）：`,
    promptTail: "请按最小改动处理：只重切被点名的刀，其余不动；镜头表同步对应行。",
    confirmHead: () => `${TITLE} 确认提示词：`,
    confirmBody: n => `改动台逐刀核对完毕：${n} 刀全部「无需调整」，剪辑方案确认无误，请直接生成。`,
  },
  en: {
    sub: "Change Board",
    loading: "Loading video…",
    hint: "The video in this folder loads automatically and plays on open. Clicking a shot plays from 3 seconds before the cut so you can see it coming. Blue bar + └ = one lyric line split into two cuts; after └ is the part this cut sings. Tick \"Loop\" first to loop a segment. If the cut feels early or late → press \"Timing off\", watch the loop and press \"Cut here\" for an exact point. Mark feedback below, then copy the prompt back to the AI. Everything runs local — nothing leaves your machine.",
    shotsTitle: "Shots · ",
    shotsRed: "After clicking a shot, the video plays from 3 seconds before the cut so you can judge it. Use the Left/Right arrow keys to adjust playback quickly.",
    loop: "Loop",
    fbTitle: "Feedback",
    sumTitle: "Summary",
    whoEmpty: "No shot selected. Click any row on the left to start.",
    kNone: "No change needed", kTiming: "Timing off", kSwap: "Swap material", kOther: "Other feedback",
    markOther: "Other",
    noLyricRow: "(no lyrics)", noLyric: "no lyrics",
    q1: "\"", q2: "\"",
    inAt: v => " @in " + v,
    notePh: "Optional note. e.g. \"a little\" / \"use a different city b-roll\"",
    copyConfirm: "Copy confirmation prompt", copyChange: "Copy change requests",
    planReady: "No changes — plan ready",
    promptPh: "The feedback summary will appear here",
    copied: "Copied to clipboard — paste it into the AI chat",
    clipBlocked: "Clipboard blocked — text selected, press Ctrl+C",
    ovlTitleDef: "Adjust cut",
    ovlDesc: "The video loops: 3 s before the cut → 3 s after this cut.",
    ovlRed: "When you see the right cut point, press \"Cut here\"",
    ovlKeys: "(keyboard: ← → seek 2 s, Space pauses).",
    ovlNowLbl: "Now ", ovlOldLbl: "s ｜ current cut ",
    ovlSet: "Cut here", ovlClear: "Clear this timing feedback", ovlCancel: "Cancel",
    loaded: (v, d) => `Video loaded: ${v} (${d}s)`,
    missing: v => `Video not found: ${OUTNAME} must sit in the same folder as the video (looking for ${v}). Put it there and refresh.`,
    tagPair: first => `same line · ${first ? "1st" : "2nd"} cut`,
    tagPairP: first => ` (${first ? "first" : "second"} cut of same line)`,
    loopState: (no, a, b, lead) => ` ｜ Looping: #${no} (${a}–${b}s${lead ? ", from 3 s before cut" : ""})`,
    marked: n => `${n} shot(s) marked`,
    ovlTitle: (no, cut) => `Shot ${no}, ${cut}s · adjust cut`,
    txtTiming: (t, d) => `timing off, move cut to ${t}s (${d < 0 ? "advance" : "delay"} ${fmt(Math.abs(d))}s)`,
    txtOther: note => `Other: ${note || "(nothing written yet)"}`,
    noteSuffix: note => ` — note: ${note}`,
    promptLine: (no, cut, quoted, gtag, txt) => `Shot ${no}, ${cut}s ${quoted}${gtag} — ${txt}`,
    promptHead: () => `${TITLE} — change requests (change board summary):`,
    promptTail: "Minimal-change handling: recut only the named shots, leave the rest untouched; sync the matching rows in the shot list.",
    confirmHead: () => `${TITLE} — confirmation prompt:`,
    confirmBody: n => `Change board review complete: all ${n} shots marked "no change needed". The edit plan is confirmed — please generate.`,
  }
};
{ const za = Object.keys(I18N.zh).filter(k => !(k in I18N.en));
  const zb = Object.keys(I18N.en).filter(k => !(k in I18N.zh));
  if (za.length || zb.length) console.warn("i18n key mismatch", za, zb); }
let lang = DEF_LANG;
try { const v = localStorage.getItem("cbLang"); if (v === "zh" || v === "en") lang = v; } catch (e) {}
function I(k, ...a) { const v = I18N[lang][k]; return typeof v === "function" ? v(...a) : v; }

// 同句两刀分组：相邻两行歌词相同（或一方包含另一方）= 一句歌词断成两刀
const norm = s => (s || "").replace(/[\s，。！？、,.!?…—「」"'：:；;（）()]/g, "");
const bare = s => (s || "").replace(/^[└↳]\s*/, "");
const GRP = SHOTS.map(() => ({size: 1, first: true}));
const FULL = SHOTS.map(s => s.lyric || "");
{
  const groups = [];
  SHOTS.forEach((s, i) => {
    const prev = groups[groups.length - 1];
    const cont = /^[└↳]/.test(s.lyric || "");
    const a = i > 0 ? norm(SHOTS[i - 1].lyric) : "", b = norm(bare(s.lyric));
    const rel = cont || (a && b && (a === b || (Math.min(a.length, b.length) >= 2 && (a.includes(b) || b.includes(a)))));
    if (prev && prev.rows[prev.rows.length - 1] === i - 1 && rel) prev.rows.push(i);
    else groups.push({rows: [i]});
  });
  groups.forEach(g => {
    const full = g.rows.map(j => bare(SHOTS[j].lyric)).join("");
    g.rows.forEach((idx, k) => { GRP[idx] = {size: g.rows.length, first: k === 0}; FULL[idx] = full; });
  });
}

function segEnd(i) {
  const s = SHOTS[i];
  if (s.dur) return s.cut + s.dur;
  if (i + 1 < SHOTS.length) return SHOTS[i + 1].cut;
  return s.cut + 5;
}

// ── 双语应用：静态文案 + 占位符 + 文档标题；切换后 updateAll() 重绘动态区 ──
function applyLang() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = TITLE + " · " + I("sub");
  $("tSub").textContent = I("sub");
  $("hintP").textContent = I("hint");
  $("shotsTitle").textContent = I("shotsTitle");
  $("shotsRed").textContent = I("shotsRed");
  $("loopLbl").textContent = I("loop");
  $("fbTitle").textContent = I("fbTitle");
  $("sumTitle").textContent = I("sumTitle");
  $("note").placeholder = I("notePh");
  $("prompt").placeholder = I("promptPh");
  $("ovlDesc").textContent = I("ovlDesc");
  $("ovlRed").textContent = I("ovlRed");
  $("ovlKeys").textContent = I("ovlKeys");
  $("ovlNowLbl").textContent = I("ovlNowLbl");
  $("ovlOldLbl").textContent = I("ovlOldLbl");
  $("ovlSet").textContent = I("ovlSet");
  $("ovlClear").textContent = I("ovlClear");
  $("ovlCancel").textContent = I("ovlCancel");
  if ($("ovl").style.display === "none") $("ovlTitle").textContent = I("ovlTitleDef");
  const cap = {none: "None", timing: "Timing", swap: "Swap", other: "Other"};
  document.querySelectorAll("#btns button").forEach(b => { b.textContent = I("k" + cap[b.dataset.k]); });
  document.querySelectorAll("#langSw button").forEach(b => b.classList.toggle("on", b.dataset.l === lang));
  renderVideoState();
}

function renderVideoState() {
  if (videoState === "ok") {
    $("vDot").className = "dot ok";
    $("vState").textContent = I("loaded", VIDEO_SRC, fmt(video.duration));
  } else if (videoState === "missing") {
    $("vDot").className = "dot warn";
    $("vState").textContent = I("missing", VIDEO_SRC);
  } else {
    $("vDot").className = "dot warn";
    $("vState").textContent = I("loading");
  }
}

function renderRows() {
  $("rows").innerHTML = SHOTS.map((s, i) => {
    const m = marks[i];
    const g = GRP[i];
    const label = m ? (m.kind === "other" ? I("markOther") : m.kind === "timing" ? "→ " + fmt(m.t) + "s" : I("kSwap")) : "";
    const gcls = g.size > 1 ? (g.first ? " grp-a" : " grp-b") : "";
    const ly = (g.size > 1 && !g.first && !/^[└↳]/.test(s.lyric || "") ? "└ " : "") + (s.lyric || I("noLyricRow"));
    return `<div class="row${gcls}${i === sel ? " sel" : ""}" data-i="${i}">
      <span class="no">#${s.no}</span>
      <span class="t">${fmt(s.cut)}s · ${(s.dur ? fmt(s.dur) : "?")}s</span>
      <span class="lyric">${ly}</span>
      <span class="mat">${s.mat || ""}${s.in ? " @" + s.in : ""}</span>
      <span class="mk">${label}</span></div>`;
  }).join("");
  document.querySelectorAll(".row").forEach(el =>
    el.addEventListener("click", () => selectRow(+el.dataset.i)));
}

function renderPanel() {
  const has = sel >= 0;
  $("btns").style.display = has ? "flex" : "none";
  $("tip").style.display = has ? "block" : "none";
  if (!has) {
    $("who").textContent = I("whoEmpty");
    $("note").style.display = "none";
    return;
  }
  const s = SHOTS[sel], m = marks[sel], g = GRP[sel];
  const gtag = g.size > 1 ? `<span class="tag">${I("tagPair", g.first)}</span>` : "";
  $("who").innerHTML = `<b>#${s.no}</b> · ${fmt(s.cut)}s · ${I("q1")}${FULL[sel] || I("noLyric")}${I("q2")}${gtag}<br>
    <span style="color:var(--muted)">${s.mat || ""}${s.in ? I("inAt", s.in) : ""}${s.mood ? " · " + s.mood : ""}</span>`;
  const note = $("note");
  note.style.display = "block";
  note.readOnly = !(m && m.kind === "other");
  note.classList.toggle("ro", note.readOnly);
  note.value = m ? (m.note || "") : "";
  document.querySelectorAll("#btns button").forEach(b =>
    b.classList.toggle("on", b.dataset.k === (m ? m.kind : "none")));
}

function renderStatus() {
  $("loopState").textContent = looping
    ? I("loopState", SHOTS[sel].no, fmt(loopStart), fmt(loopEnd), loopStart > 0) : "";
  const n = Object.keys(marks).length;
  const btn = $("copyBtn");
  btn.textContent = n ? I("copyChange") : I("copyConfirm");
  btn.className = n ? "primary" : "ok";
  $("copyState").innerHTML = n
    ? `<span class="dot bad"></span>${I("marked", n)}`
    : `<span class="dot ok"></span>${I("planReady")}`;
  $("prompt").value = buildPrompt();
}

function updateAll() { renderRows(); renderPanel(); renderStatus(); }

function selectRow(i) {
  if (sel === i) { // 再点同一行 = 停止循环
    looping = false; sel = -1; updateAll(); return;
  }
  sel = i;
  looping = $("loopChk").checked; // 勾上「循环播放」才循环，对本次点击生效
  loopStart = Math.max(0, SHOTS[i].cut - LEAD); // 弹幕定位式：先看到切入前 3 秒
  loopEnd = segEnd(i);
  if (video.src) {
    video.currentTime = loopStart;
    video.play().catch(() => {});
  }
  updateAll();
}

function mark(kind) {
  if (sel < 0) return;
  const cur = marks[sel];
  if (kind === "none") delete marks[sel];                 // 无需调整 = 回到默认
  else marks[sel] = {kind, note: cur ? (cur.note || "") : ""};
  updateAll();
}

function buildPrompt() {
  const keys = Object.keys(marks).map(Number).sort((a, b) => a - b);
  if (!keys.length) {
    return I("confirmHead") + "\n" + I("confirmBody", SHOTS.length);
  }
  const lines = keys.map(i => {
    const s = SHOTS[i], m = marks[i], g = GRP[i];
    let txt;
    if (m.kind === "timing") {
      const d = m.t - s.cut;
      txt = I("txtTiming", fmt(m.t), d);
    } else if (m.kind === "other") {
      txt = I("txtOther", m.note);
    } else {
      txt = I("kSwap");
    }
    if (m.kind !== "other" && m.note) txt += I("noteSuffix", m.note);
    const gtag = g.size > 1 ? I("tagPairP", g.first) : "";
    const quoted = I("q1") + (FULL[i] || I("noLyric")) + I("q2");
    return I("promptLine", s.no, fmt(s.cut), quoted, gtag, txt);
  });
  return I("promptHead") + "\n" +
    lines.map((l, i) => `${i + 1}. ${l}`).join("\n") +
    "\n" + I("promptTail");
}

document.querySelectorAll("#btns button").forEach(b =>
  b.addEventListener("click", () => (b.dataset.k === "timing" ? openTiming() : mark(b.dataset.k))));
$("note").addEventListener("input", () => {
  if (sel < 0) return;
  if (!marks[sel]) marks[sel] = {kind: "other", note: ""};
  marks[sel].note = $("note").value;
  renderRows(); renderStatus();
});

video.addEventListener("loadedmetadata", () => {
  videoState = "ok";
  renderVideoState();
});
video.addEventListener("error", () => {
  videoState = "missing";
  renderVideoState();
});

video.addEventListener("timeupdate", () => {
  if (looping && video.currentTime >= loopEnd - 0.03) video.currentTime = loopStart;
  if ($("ovl").style.display !== "none") $("ovlNow").textContent = fmt(video.currentTime);
  // LRC 式自动跟随：没点分镜时，列表跟着播放走到当前这一刀（防止忘了选行、改错刀）
  const ta = $("note");
  if ($("ovl").style.display === "none" && !looping && SHOTS.length &&
      !(document.activeElement === ta && ta && !ta.readOnly)) {
    const t = video.currentTime;
    let idx = 0;
    for (let i = 0; i < SHOTS.length; i++) if (t >= SHOTS[i].cut - 1e-6) idx = i;
    if (idx !== sel) {
      const inLead = sel >= 0 && t < SHOTS[sel].cut && t >= SHOTS[sel].cut - LEAD;
      if (!inLead) {
        sel = idx;
        renderRows();
        renderPanel();
        const el = document.querySelectorAll(".row")[sel];
        if (el && el.scrollIntoView) el.scrollIntoView({block: "nearest"});
      }
    }
  }
});

// ── 「时机不对」：循环看，点「调整到这里」定点 ──
function openTiming() {
  if (sel < 0) return;
  const s = SHOTS[sel];
  $("ovlTitle").textContent = I("ovlTitle", s.no, fmt(s.cut));
  $("ovlOld").textContent = fmt(s.cut);
  $("ovlClear").style.display = marks[sel] && marks[sel].kind === "timing" ? "inline-block" : "none";
  $("ovl").style.display = "flex";
  loopStart = Math.max(0, s.cut - LEAD);
  loopEnd = Math.min(video.duration || s.cut + 30, segEnd(sel) + TAIL);
  looping = true;
  if (video.src) { video.currentTime = loopStart; video.play().catch(() => {}); }
  renderStatus();
}
function closeTiming() {
  $("ovl").style.display = "none";
  looping = $("loopChk").checked && sel >= 0;
  if (looping) { loopStart = Math.max(0, SHOTS[sel].cut - LEAD); loopEnd = segEnd(sel); }
  renderStatus();
}
$("ovlSet").addEventListener("click", () => {
  if (sel < 0) return;
  const t = Math.round(video.currentTime * 100) / 100;
  const cur = marks[sel] || {};
  marks[sel] = {kind: "timing", t, note: cur.note || ""};
  closeTiming();
  updateAll();
});
$("ovlCancel").addEventListener("click", closeTiming);
$("ovlClear").addEventListener("click", () => {
  delete marks[sel];
  closeTiming();
  updateAll();
});

// ── 键盘：← → 快退/快进 2 秒，空格暂停/继续（全局 + 弹窗通用；「我有别的想法」输入框里不启用）──
document.addEventListener("keydown", e => {
  const ta = $("note");
  if (document.activeElement === ta && ta && !ta.readOnly) return;   // 正在输入文字
  const v = $("video");
  if (e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === " ") {
    e.preventDefault();
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  }
  if (e.key === "ArrowLeft") v.currentTime = Math.max(0, v.currentTime - 2);
  else if (e.key === "ArrowRight") v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 2);
  else if (e.key === " ") { if (v.paused) v.play().catch(() => {}); else v.pause(); }
});

$("copyBtn").addEventListener("click", async () => {
  const text = buildPrompt();
  $("prompt").value = text;
  try {
    await navigator.clipboard.writeText(text);
    $("copyState").innerHTML = '<span class="dot ok"></span>' + I("copied");
  } catch (err) {
    $("prompt").select();
    document.execCommand("copy");
    $("copyState").innerHTML = '<span class="dot warn"></span>' + I("clipBlocked");
  }
});

$("loopChk").addEventListener("change", () => {
  try { localStorage.setItem("cbLoop", $("loopChk").checked ? "1" : "0"); } catch (e) {}
  if (!$("loopChk").checked) looping = false; // 取消勾选立即停止当前循环
  renderStatus();
});
try { $("loopChk").checked = localStorage.getItem("cbLoop") === "1"; } catch (e) {}

// ── 右上角「中 / EN」开关：切换即时生效，手动选择记在本地（识别失效时的兜底）──
document.querySelectorAll("#langSw button").forEach(b =>
  b.addEventListener("click", () => {
    lang = b.dataset.l;
    try { localStorage.setItem("cbLang", lang); } catch (e) {}
    applyLang();
    if ($("ovl").style.display !== "none" && sel >= 0)
      $("ovlTitle").textContent = I("ovlTitle", SHOTS[sel].no, fmt(SHOTS[sel].cut));
    updateAll();
  }));

applyLang();
video.src = VIDEO_SRC;
updateAll();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots_md", help="镜头表.md 路径")
    ap.add_argument("--title", default=None, help="标题，如《推开世界的门》混剪")
    ap.add_argument("--video", default=None, help="成片文件名（默认自动找输出目录里的视频）")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="初始界面语言（默认 zh；页面右上角「中 / EN」可随时切换）")
    ap.add_argument("-o", "--out", default=None, help="输出 html（默认同目录 改动台.html／changeboard.html）")
    args = ap.parse_args()

    md = Path(args.shots_md)
    rows = parse_shots(md.read_text(encoding="utf-8"))
    title = args.title or md.parent.name
    out = Path(args.out) if args.out else md.parent / ("changeboard.html" if args.lang == "en" else "改动台.html")
    video_name = detect_video(out.parent, args.video, md.parent.name)

    html = (HTML
            .replace("__SHOTS__", json.dumps(rows, ensure_ascii=False))
            .replace("__VIDEOJSON__", json.dumps(video_name, ensure_ascii=False))
            .replace("__TITLEJS__", json.dumps(title, ensure_ascii=False))
            .replace("__TITLE__", title)
            .replace("__OUTNAME__", out.name)
            .replace("__LANG__", args.lang))
    out.write_text(html, encoding="utf-8")
    print("OK %s  分镜 %d 刀 · 成片 %s · 界面 %s" % (out, len(rows), video_name, args.lang))


if __name__ == "__main__":
    main()
