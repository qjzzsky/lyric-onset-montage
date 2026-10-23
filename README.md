# Lyric-Onset Montage

[中文简体](./README.zh-CN.md)

**Cut footage to the sung word — not to the beat, and not to the subtitle.**

A skill for AI agents that turns a song plus a folder of raw footage into a montage whose every cut lands on the first consonant of a lyric line. It measures the onset from the audio, keeps shot selection and timing as two separate decisions, and hands back evidence you can check instead of adjectives you have to trust.

## Install

```bash
npx skills add qjzzsky/lyric-onset-montage
```

That is the path tested on this repo: skills.sh clones it, finds one skill and installs `lyric-onset-montage` for the agents it detects (Claude Code, Codex, Cursor, Amp, Cline and others).

With the GitHub CLI, name the agent you want:

```bash
gh skill install qjzzsky/lyric-onset-montage lyric-onset-montage --agent codex
```

Hermes is not in that agent list — copy the folder instead: take `skills/lyric-onset-montage/` from the repo and put it in your local skills directory, then `hermes skills list` should show `lyric-onset-montage`.

---

## Read the footage before you label it

![Four cuts: steps beside a ramp → the ramp with handrails → the driver pulling the ramp out → off the train](showcase/骄傲的少年-115s/sequence.png)

Selection is not guessing from file names. Before cutting, the skill reads the footage like a reference library:

- **Sample frames.** One frame per second, or a contact sheet: what is actually in this clip — empty scenery, crowds, faces, plates, readable phone numbers?
- **Transcribe the audio.** Decide whether it is speech or a lyric. Speech only tells you what the clip is about; it never sets a cut. Lyrics set line boundaries and onsets.
- **Tag it.** Mark every clip `★ golden window`, `● usable` or `⛔ unusable`; clips you drop get tagged too.
- **Split a file into windows.** A file is not one item: divide it by content and record the time range and usability of each piece — one file often supplies several unrelated cuts.
- **Write it into the index.** Unusable clips go in tagged `⛔` so the next song cannot pick them; the index is reused, so from the second song on there is no re-survey.

How deep the survey goes scales with the library: a handful of short clips get a full pass; dozens of clips or two hours of material get a coarse pass first, then a question about a full pass with a time estimate.

Once the footage is sorted, a lyric line can be broken into several shots. The four cuts above are what sits under 「转眼间 / 一切都已改变 / 新的起点」, in film order: steps beside a ramp → the ramp now carrying handrails → the driver pulling the blue ramp out → off the train.

Concretely, in the example above, the handrail that appears in the second frame is the plainest image of 「一切都已改变」 — not change in the abstract, but something you can hold on to.

「新的起点」 spans the last two cuts: shot 15 is one continuous take, from the car door and the driver bending to pull the ramp out to the ramp flat on the ground; shot 16 cuts to the platform. That is why every line gets 3–4 first choices plus 3–6 alternates, with the reason for each, and a cut only after you nod.

---

## Then the cut: beat grid vs measured onsets

![Cut alignment: beat grid vs measured lyric onsets](showcase/骄傲的少年-115s/cut-proof.png)

Top track: the beat grid. Bottom track: measured onsets. The red lines are where the cuts actually are.

In this 115-second edit the beat grid and the sung word disagree by **222 ms at the median, 346 ms at worst** (n = 20) — about half a beat — so cutting to the beat is audibly wrong, and cutting to a subtitle timestamp is wrong by a smaller but still audible margin.

> **How to read the numbers:** `A` = cut − measured onset (is this cut right). `B` = nearest beat − measured onset (what cutting to the beat would cost). `B` is the independent comparison; `A` is measured with the same family of detectors that placed the cut, so a small `A` proves consistency, not correctness. **The independent check is your ear** — every case below was accepted or corrected by a human listening, and those corrections are logged.

How each of the three evidence figures is read and made: [`showcase/证据图例.md`](showcase/证据图例.md).

---

## Three things this does that a beat-synced editor does not

1. **Cuts land on the sung onset, measured from the audio.** Subtitle and LRC timestamps are used only to narrow the search window: they typically start **0.1–0.27 s before** the voice. A cut placed on the subtitle is a cut that arrives early.

2. **Timing and shot selection are judged separately.** A montage can be frame-accurate and still be full of empty shots; it can also have perfect shots and be 200 ms early on every line. Two metrics, two checks, never averaged into one score.

3. **One image per question.** One answers "is this cut on the word", another answers "were these shots the right choice"; neither substitutes for the other.

---

## Four cases that trace how it grew

Each case is the skill at a different stage — what it could do, and what it still got wrong. The third column is the environment that version ran in, for reference.

| # | Case | Environment | Route | What it proves |
| - | --- | --- | --- | --- |
| ① | [`意外-20261018`](showcase/意外-20261018/) | Hermes Agent · Xiaomi MiMo V2.6 | No lyric source: cut per line first, then re-cut on the onset | **Where it started.** Moving from "cut per sentence" to "cut on the word"; the beat grid was off by 160–369 ms |
| ② | [`骄傲的少年-115s`](showcase/骄傲的少年-115s/) | DeepSeek Harness · DeepSeek V4.1 | Album LRC ↔ audio cross-correlation to solve the offset (**+1.83 s**), 20 lines re-checked at a **0.10 s** median | **Time base solved**, and the A/B split became two separate metrics |
| ③ | [`推开世界的门-55s`](showcase/推开世界的门-55s/) | Hermes Agent · DeepSeek V4.1 | 55-second chorus slice, 16 cuts, then **six rounds / 9 real edits** after delivery | **Revision as a first-class step.** The only case with a full "delivered, then changed" log — including the round where the wrong cuts were edited because of an off-by-one in the figure labels |
| ④ | [`快乐小神仙-176s`](showcase/快乐小神仙-176s/) | Hermes Agent · DeepSeek V4.1 | No subtitle track: 37 lyric segments detected from burned-in subtitles | **The hard case.** 47 cuts, 176.00 s, zero revisions — and the case where the metrics were openly called out as self-referential |

Specs, per-cut tables and self-checks live inside each folder.

Track credits: 《意外》 — 薛之谦 (words and music 杨子朴) ｜ 《骄傲的少年》 — 南征北战NZBZ (words 赵辰龙, music 汀洋) ｜ 《推开世界的门》 — 杨乃文 (words and music 火星电台 / 黄少峰) ｜ 《快乐小神仙》 — 天唱组合 (words 张藜, music 肖白). All rights stay with their owners; these four cases are technical write-ups only. Footage is referred to by alias (`S01`…); original file names are not published.

---

## Install

The skill is a directory the agent reads; there is no daemon and no API key.

```text
# Hermes Agent
copy skills/lyric-onset-montage/  →  <hermes profile>/skills/media/

# Claude Code and compatible agents
cp -r skills/lyric-onset-montage  ~/.claude/skills/

# Anything else
point the agent at skills/lyric-onset-montage/SKILL.md and let it read references/
```

Everything the agent needs is inside `skills/lyric-onset-montage/` — `SKILL.md`, `references/`, `scripts/`, `templates/`. The README is for you; the skill is for the agent.

---

## Requirements

|  | Minimum | Recommended | Why |
| --- | --- | --- | --- |
| **Model: reads images** | required | multimodal | Contact sheets, candidate frames and burned-subtitle strips are all judged by looking |
| **Model: context** | ≥64k | ≥200k | One 47-cut table plus the 27-step workflow plus `references/` |
| **Tools: shell** | required | required | ffmpeg, ffprobe, the Python scripts |
| **Tools: file read/write** | required | required | Reads the footage folder, writes cuts and tables |
| **Tools: background jobs** | helpful | required | Encoding takes tens of minutes and must keep reporting |
| **Runtime** | ffmpeg + ffprobe + Python 3.10+ | + numpy / scipy / matplotlib in a project venv | `check_cut.py` produces the A/B figures and the contact sheet |
| **Footage** | your own video | an indexed library | An index saves re-surveying the same footage for every song |
| **Network** | untested | untested | The author's environment has always been online; running fully offline has not been verified. The skill itself never fetches anything |
| **Downloader** | not needed | not needed | This skill ships no downloader of any kind |

**Tested on** (author's own runs — each row below produced a finished edit):

| Host | Model | Result |
| --- | --- | --- |
| Hermes Agent (Nous Research) | Xiaomi MiMo V2.6 | ✅ |
| Hermes Agent | DeepSeek V4.1 | ✅ |
| DeepSeek Harness (DSH) | DeepSeek V4.1 | ✅ |

Model tiers inside a series differ by size and cost; the skill runs on either. Pick the tier by the job, not by the README.

---

## Ask for it in three lines

```text
Cut a lyric-synced montage from <music file or media stream path>.
The footage is in <footage directory path> — analyse what is in that folder first.
Range: <whole song / up to the first chorus / until a named line>.
```

That is the whole brief. Everything else — surveying the footage, picking lyric sources, measuring onsets, building the shot table — is the skill's job.

---

## Workflow: 27 steps in five stages

Full detail, including what failure looks like at each step, in [`references/workflow.md`](skills/lyric-onset-montage/references/workflow.md).

| Stage | Steps | What it produces | Typical failure |
| --- | --- | --- | --- |
| **A. Scope** | 1–5 brief · range and end point · audio · footage survey · environment check | Range, 48 kHz audio, `素材清单.md` | Surveying at "one frame every 10 s" and writing windows from it |
| **B. Timeline** | 6–12 lyric sources · line boundaries · onsets · auxiliary checks · time base · onset table · cross-check | `字头表.csv` with a confidence column | Trusting subtitle timestamps as onsets |
| **C. Selection** | 13–17 candidates · frame checks · context check · preview · approval | 3–4 first choices + 3–6 alternates per line | Cutting with one option per line, so one bad choice re-renders everything |
| **D. Assembly** | 18–22 shot table · per-cut arithmetic · cuts · concat + mux · self-check | Seamless timeline, single audio track | `-c copy` dropping frames, `-shortest` clipping the tail |
| **E. Delivery** | 23–27 deliver · collect notes · minimal edits · change log · write back to the index | Final video, contact sheet, shot table, self-check, browser change board (`改动台.html`) | Rebuilding the whole edit for one cut |

Stage E ships one more thing: a **change board** built from the shot table, which plays the edit cut by cut so you can point at a frame instead of counting seconds — see [Refine it in the browser](#refine-it-in-the-browser).

---

## Revise it by talking

The edit is not frozen when it is delivered. Say which cut and what is wrong:

```text
Line "<a line of the lyric>" doesn't match the shot — replace that shot.
Shot <n>: cut a little early, move it later.
Shot <n>: I can't see it before it's gone, keep one of the two.
```

Three phrasings cover almost every revision: swap the footage, move the cut, or pick one moment inside a single clip. Only the named cuts are re-cut; the other cut files are reused, and the delivery includes proof that nothing else moved.

---

## Refine it in the browser

![Bilingual change board: Chinese UI on the left, English UI on the right, the same cut #9 selected in both](showcase/推开世界的门-55s-v2/改动台-双语对照.png)

`templates/build_changeboard.py` reads the shot table and writes `改动台.html` into the same folder as the final video. One file, no server, no network, no access to the footage library.

- **Click a shot.** Playback starts 3 seconds before its cut, so you see what leads into it.
- **Four states per cut.** No change (default) / timing off / swap the footage / something else. Only that cut is marked.
- **"Timing off" loop.** It repeats the three seconds either side of the cut; hit "adjust here" where it should land and that time goes straight into the prompt. Say "a bit early" once or twice — if the number is still off, stop guessing and point at the frame.
- **Auto-follow.** The list and the panel follow playback like a lyric sheet, so a note cannot land on the wrong cut.
- **Keyboard.** ← → skip 2 seconds, space pauses — everywhere except while typing.
- **Two languages.** The `中 / EN` switch flips every label and the wording of the prompt; `--lang en` opens it in English.
- **Two copy buttons.** Green when nothing changed (confirm and render), blue when something did (copy the change list).

The prompt it copies is the same "which cut, what is wrong" brief the skill accepts by voice — the page only removes the guessing. Worked example: [`showcase/推开世界的门-55s-v2/`](showcase/推开世界的门-55s-v2/) — seven cuts picked by ear on this page, every one verified to a frame.

---

## What it does not do

- **It does not download music or video.** You supply the files. The skill has no search, no scraper, no bypass of any platform.
- **It cannot hear the way you do.** For legato lines with no breath before the first word, the detector returns a candidate — the cut is marked `⚠ unconfirmed` and left for your ear. The skill says so instead of pretending.
- **It does not decide who may appear on camera.** If a face, a plate or a sign might be a problem, it asks and offers an alternative shot; it does not blur the problem and call it solved.
- **It does not replace your taste.** Selection is ranked and previewed, then approved by you.
- **A is not an independent measurement.** See the note under the first image.

---

## Licence, credits, responsibility

License: [MIT](LICENSE). Built with FFmpeg, faster-whisper, numpy, scipy and matplotlib — each credited with its own licence in [`CREDITS.md`](CREDITS.md).

### About the author

**qjzzsky**

- GitHub: [qjzzsky](https://github.com/qjzzsky)
- Website: [qjzzsky.com](https://qjzzsky.com)
- Bilibili: [space.bilibili.com/1546459](https://space.bilibili.com/1546459)
- Weibo: [weibo.com/u/1074366780](https://weibo.com/u/1074366780)

Built with [Hermes Agent](https://github.com/NousResearch/hermes-agent) and DeepSeek Harness — carried by Xiaomi MiMo V2.6 and DeepSeek V4.1. Skills, scripts and case studies authored, tested and published with their help.

中文版：[README.zh-CN.md](README.zh-CN.md)

---

## Disclaimer

This skill is a tool that executes the user's own instructions.

Every video it produces is built from footage the user supplies and prompts the user writes. The author takes no part in the creative decisions and accepts no responsibility for the truthfulness, completeness or accuracy of the output, nor for any stance or intent it may express.

Users are responsible for ensuring they hold the rights to the footage, music and lyrics they supply; any copyright or other liability arising from their use rests with them.
