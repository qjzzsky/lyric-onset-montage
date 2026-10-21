#!/usr/bin/env python3
"""faster-whisper base int8 转写。
用法: <venv python> transcribe_fw.py <16k单声道.wav> [段起始秒偏移]
faster-whisper 要装在工程自己的 venv 里（系统 python 通常没有）：
  <venv>/Scripts/python.exe transcribe_fw.py a.wav
长音频分段转写时传第二个参数，把时间戳平移回全片坐标。"""
import sys, time
from faster_whisper import WhisperModel

wav = sys.argv[1]
offset = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
t0 = time.time()
model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=8)
segments, info = model.transcribe(wav, vad_filter=True, beam_size=5)
print(f"# lang={info.language} prob={info.language_probability:.2f}")
for s in segments:
    print(f"[{s.start+offset:7.2f} -> {s.end+offset:7.2f}] {s.text.strip()}")
print(f"# done in {time.time()-t0:.1f}s")
