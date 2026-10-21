# Credits

This skill calls other tools rather than bundling them. Each keeps its own licence.

| Tool | Used for | Licence | Source |
|---|---|---|---|
| [FFmpeg](https://ffmpeg.org/) (incl. `ffprobe`) | Slice, encode, concat, mux, probe | LGPL-2.1-or-later (some builds GPL) | ffmpeg.org |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Speech-to-text for lyric **wording only** — never for timing | MIT | GitHub |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | Inference backend for faster-whisper | MIT | GitHub |
| [NumPy](https://numpy.org/) | Envelope, correlation, frame arithmetic | BSD-3-Clause | numpy.org |
| [SciPy](https://scipy.org/) | Filters (band-pass on the RMS envelope) | BSD-3-Clause | scipy.org |
| [matplotlib](https://matplotlib.org/) | Contact sheets and figures in `check_cut.py` | PSF-based (matplotlib licence) | matplotlib.org |

`check_cut.py`, `probe_pts.py`, `solve_audio_offset.py`, `burned_subtitles.py`,
`onset_beat_probe.py`, `cut_ruler.py`, `srt_to_cuts.py`, `templates/build_mix.py` and the
figure scripts under `showcase/_tools/` (`render_cutproof.py`, `render_jiaoao_bilingual.py`,
`render_sequence.py`, `render_legend.py`) are original to this repository (MIT).

## Music used in the case studies

Each case is a technical write-up of an edit made to the author's own footage. The songs are
third-party works, credited here, and are **not** redistributed in any form:

| Case | Song | Performer | Words / music |
|---|---|---|---|
| ① | 《意外》 | 薛之谦 | words and music 杨子朴 |
| ② | 《骄傲的少年》 | 南征北战NZBZ | words 赵辰龙 / music 汀洋 |
| ③ | 《推开世界的门》 | 杨乃文 | words and music 火星电台 / 黄少峰 |
| ④ | 《快乐小神仙》 | 天唱组合 | words 张藜 / music 肖白 |

All rights in the songs, the performances and the recordings stay with their owners. Only
still frames, waveform plots, lyrics fragments needed to show alignment, and timing tables
appear in this repository.

## About the case studies

The four folders under `showcase/` are records of real edits. The **footage is the author's
own**; the **music and lyrics are third-party works**, quoted only as short excerpts for
alignment and verification. No audio or video file from any song is redistributed here —
only still frames, waveform plots and timing tables. If you reuse a case, the song rights are
yours to clear, not the author's to grant.
