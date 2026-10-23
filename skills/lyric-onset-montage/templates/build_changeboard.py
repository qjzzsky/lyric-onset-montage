# -*- coding: utf-8 -*-
"""
build_changeboard.py — 从 镜头表.md 生成 改动台.html

用法：
    python build_changeboard.py 镜头表.md [--title "《歌名》混剪"] [--video 成片.mp4] [-o 改动台.html]

规矩（与技能一致）：
- 列按表头名字定位（#/序号、切点、时长、歌词、素材、入点），不按列位置。
- 成片自动挂同目录那一支（多个视频时用 --video 指定）：打开即播，刷新不断。
- 数据内嵌 JSON：不联网、不碰素材库。
- 点分镜从切点前 3 秒起播放（看清切入，类似弹幕定位）；列表头复选框勾上「循环播放」才循环。同句两刀的续刀行以 └ 开头（如 └的门）。
- 「时机不对」弹窗：循环看这一刀前后几秒，点「调整到这里」把目标切点记进提示词。
- 键盘：← → 快退/快进 2 秒、空格暂停（全局+弹窗通用；「我有别的想法」输入框聚焦时不启用）。按钮第一格「无需调整」是默认态；输入框未选「我有别的想法」时只读。
- 列表 LRC 式自动跟随：播放到哪刀，列表与右侧面板自动跟到哪刀（只在没点分镜时跟；点过行的预览/循环、弹窗打开、正在输入时不抢选中，选中刀的切点前 3 秒引导段里也不换）。
- 汇总按钮两态：无改动＝绿色「复制确认提示词」（确认无误、可直接生成）；有改动＝蓝色「复制改动提示词」。
- 页面只收集改动意见、不改片；输出的提示词贴回 AI 走「最小改动」流程。
- 待做：界面语言按用户提示词语言判定（中文→中文界面，英文→英文界面），先把中文版定稿。
"""
import argparse
import json
import re
from pathlib import Path

COL_ALIASES = {
    "no": ("#", "序号", "刀号", "编号"),
    "cut": ("切点",),
    "dur": ("时长",),
    "lyric": ("歌词",),
    "mat": ("素材",),
    "in": ("入点",),
    "mood": ("情绪",),
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
                key = name.strip()
                for k, aliases in COL_ALIASES.items():
                    if key in aliases and k not in colmap:
                        colmap[k] = i
                for k in ("cut", "lyric", "dur", "mat", "mood"):
                    if key.startswith(COL_ALIASES[k][0]):
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
<title>__TITLE__ · 改动台</title>
<style>
:root{--blue:#1f6feb;--ink:#16283f;--muted:#5b6b80;--line:#d7e1ee;--bg:#f4f7fb;--card:#fff;
--ok:#24a148;--warn:#f0a202;--bad:#e2574c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:18px 20px 48px}
h1{font-size:20px;margin:0 0 2px}
h1 .sub{font-size:13px;color:var(--muted);font-weight:400;margin-left:8px}
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
  <h1>__TITLE__<span class="sub">改动台</span></h1>
  <div class="status"><span class="dot warn" id="vDot"></span><span id="vState">正在载入成片…</span>
    <span id="loopState"></span></div>
  <p class="hint">成片自动带同文件夹那一支，打开即播。点分镜 = 从切点前 3 秒起播放看清切入（类似弹幕定位）；蓝竖条 + └ = 同一句歌词断成两刀，└ 后写这一刀唱的部分。勾上「循环播放」后点分镜才循环这一段。觉得切入时机不对 → 点「时机不对」，循环看着点「调整到这里」精确定点。在下面选改动，最后复制提示词贴回 AI。全程本地，不联网。</p>
  <div class="video-box"><video id="video" controls preload="metadata"></video></div>
  <div class="grid">
    <div class="ovl" id="ovl" style="display:none">
      <div class="modal">
        <h3 id="ovlTitle">调整切点</h3>
        <p>视频在循环：切点前 3 秒 → 这一刀后 3 秒。<span class="redhint">看到该切的位置，点「调整到这里」</span>（键盘 ← → 快退/快进 2 秒，空格暂停）。<br>
        当前 <span class="now" id="ovlNow">0.00</span>s ｜ 现在的切点 <span class="now" id="ovlOld">0.00</span>s</p>
        <div class="btns">
          <button class="primary" id="ovlSet">调整到这里</button>
          <button id="ovlClear" style="display:none">清除这刀的时机意见</button>
          <button id="ovlCancel">取消</button>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>分镜 · <span class="redhint">点击分镜后，视频将从分镜的前三秒处开始播放，以便分辨。可以通过键盘的左和右键，快速对播放进度进行调整。</span><span class="h2fill"></span><label class="loopbox"><input type="checkbox" id="loopChk"> 循环播放</label></h2>
      <div class="rows" id="rows"></div>
    </div>
    <div>
      <div class="card">
        <h2>改动意见</h2>
        <div class="panel" id="panel">
          <p class="who" id="who">还没选分镜。点左边任意一行开始。</p>
          <div class="btns" id="btns" style="display:none">
            <button data-k="none" class="on">无需调整</button>
            <button data-k="timing">时机不对</button>
            <button data-k="swap">换素材</button>
            <button data-k="other">我有别的想法</button>
          </div>
          <textarea id="note" placeholder="补充说明，可不填。例：一点点 / 换个城市空镜" style="display:none"></textarea>
          <p class="tip" id="tip" style="display:none"></p>
        </div>
      </div>
      <div class="card foot">
        <h2>汇总</h2>
        <div class="panel">
          <button class="ok" id="copyBtn">复制确认提示词</button>
          <span class="status" style="margin:0 0 0 8px" id="copyState"><span class="dot ok"></span>无需调整，方案就绪</span>
          <textarea class="prompt" id="prompt" readonly placeholder="改动意见汇总后会显示在这里"></textarea>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
const SHOTS = __SHOTS__;
const TITLE = "__TITLE__";
const VIDEO_SRC = __VIDEOJSON__;
const KIND = {timing:"时机不对", swap:"换素材"};
const LEAD = 3.0; // 切点前几秒起播（弹幕定位式）
const TAIL = 3.0; // 时机调整循环里，这一刀后再播几秒
let sel = -1, looping = false, loopStart = 0, loopEnd = 0;
const marks = {};
const $ = id => document.getElementById(id);
const video = $("video");
const fmt = t => (Math.round(t * 100) / 100).toFixed(2);

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

function renderRows() {
  $("rows").innerHTML = SHOTS.map((s, i) => {
    const m = marks[i];
    const g = GRP[i];
    const label = m ? (m.kind === "other" ? "其他" : m.kind === "timing" ? "→ " + fmt(m.t) + "s" : KIND[m.kind]) : "";
    const gcls = g.size > 1 ? (g.first ? " grp-a" : " grp-b") : "";
    const ly = (g.size > 1 && !g.first && !/^[└↳]/.test(s.lyric || "") ? "└ " : "") + (s.lyric || "（无词）");
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
    $("who").textContent = "还没选分镜。点左边任意一行开始。";
    $("note").style.display = "none";
    return;
  }
  const s = SHOTS[sel], m = marks[sel], g = GRP[sel];
  const gtag = g.size > 1 ? `<span class="tag">同句${g.first ? "前刀" : "后刀"}</span>` : "";
  $("who").innerHTML = `<b>#${s.no}</b> · ${fmt(s.cut)}s · 「${FULL[sel] || "无词"}」${gtag}<br>
    <span style="color:var(--muted)">${s.mat || ""}${s.in ? " @入点 " + s.in : ""}${s.mood ? " · " + s.mood : ""}</span>`;
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
    ? ` ｜ 循环中：#${SHOTS[sel].no}（${fmt(loopStart)}–${fmt(loopEnd)}s${loopStart > 0 ? "，切点前 3 秒起" : ""}）` : "";
  const n = Object.keys(marks).length;
  const btn = $("copyBtn");
  btn.textContent = n ? "复制改动提示词" : "复制确认提示词";
  btn.className = n ? "primary" : "ok";
  $("copyState").innerHTML = n
    ? `<span class="dot bad"></span>已标记 ${n} 刀`
    : `<span class="dot ok"></span>无需调整，方案就绪`;
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
    return `${TITLE} 确认提示词：\n改动台逐刀核对完毕：${SHOTS.length} 刀全部「无需调整」，剪辑方案确认无误，请直接生成。`;
  }
  const lines = keys.map(i => {
    const s = SHOTS[i], m = marks[i], g = GRP[i];
    let t;
    if (m.kind === "timing") {
      const d = m.t - s.cut;
      t = `时机不对，切点调整到 ${fmt(m.t)}s（${d < 0 ? "提前" : "推迟"} ${fmt(Math.abs(d))}s）`;
    } else if (m.kind === "other") {
      t = "其他：" + (m.note || "（没写内容，待补）");
    } else {
      t = KIND[m.kind];
    }
    if (m.kind !== "other" && m.note) t += "；备注：" + m.note;
    const gtag = g.size > 1 ? `（同句${g.first ? "前刀" : "后刀"}）` : "";
    return `第 ${s.no} 刀 ${fmt(s.cut)}s「${FULL[i] || "无词"}」${gtag}——${t}`;
  });
  return `${TITLE} 改动意见（改动台汇总）：\n` +
    lines.map((l, i) => `${i + 1}. ${l}`).join("\n") +
    `\n请按最小改动处理：只重切被点名的刀，其余不动；镜头表同步对应行。`;
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
  $("vDot").className = "dot ok";
  $("vState").textContent = `成片已载入：${VIDEO_SRC}（${fmt(video.duration)}s）`;
});
video.addEventListener("error", () => {
  $("vDot").className = "dot warn";
  $("vState").textContent = `成片没找到：改动台.html 要和成片放在同一个文件夹（现在找的是 ${VIDEO_SRC}），放好后刷新`;
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
  $("ovlTitle").textContent = `第 ${s.no} 刀 ${fmt(s.cut)}s · 调整切点`;
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
    $("copyState").innerHTML = '<span class="dot ok"></span>已复制到剪贴板，去 AI 对话里粘贴';
  } catch (err) {
    $("prompt").select();
    document.execCommand("copy");
    $("copyState").innerHTML = '<span class="dot warn"></span>剪贴板受限，已选中文本，Ctrl+C 复制';
  }
});

$("loopChk").addEventListener("change", () => {
  try { localStorage.setItem("cbLoop", $("loopChk").checked ? "1" : "0"); } catch (e) {}
  if (!$("loopChk").checked) looping = false; // 取消勾选立即停止当前循环
  renderStatus();
});
try { $("loopChk").checked = localStorage.getItem("cbLoop") === "1"; } catch (e) {}

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
    ap.add_argument("-o", "--out", default=None, help="输出 html（默认同目录 改动台.html）")
    args = ap.parse_args()

    md = Path(args.shots_md)
    rows = parse_shots(md.read_text(encoding="utf-8"))
    title = args.title or md.parent.name
    out = Path(args.out) if args.out else md.parent / "改动台.html"
    video_name = detect_video(out.parent, args.video, md.parent.name)

    html = (HTML
            .replace("__SHOTS__", json.dumps(rows, ensure_ascii=False))
            .replace("__VIDEOJSON__", json.dumps(video_name, ensure_ascii=False))
            .replace("__TITLE__", title.replace('"', '\\"')))
    out.write_text(html, encoding="utf-8")
    print("OK %s  分镜 %d 刀 · 成片 %s" % (out, len(rows), video_name))


if __name__ == "__main__":
    main()
