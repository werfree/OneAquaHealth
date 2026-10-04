#!/usr/bin/env python
"""Synthesize narration audio, one WAV per scene, from video/narration.md.

Reads the spoken (bold) lines of each `## Scene N — … · a–b` block, runs piper
locally, writes `video/_build/wavs/scene-NN.wav`, and prints the duration of
each so the assembler can size the video clips to match exactly.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NARR = REPO / "video" / "narration.md"
OUT = REPO / "video" / "_build" / "wavs"
VOICE = REPO / "video" / "_capture" / "voices" / "en_US-lessac-medium.onnx"
PY = REPO / ".venv" / "bin" / "python"


def scene_blocks(text: str):
    """Yield (scene_no, spoken_text)."""
    headers = list(re.finditer(r"^## Scene (\d+) — .*? · (\d+:\d+)–(\d+:\d+)\s*$", text, re.M))
    for i, m in enumerate(headers):
        stop = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[m.end():stop].split("### Word count")[0]
        spoken = " ".join(
            ln.strip().strip("*")
            for ln in body.splitlines()
            if ln.strip().startswith("**") and ln.strip().endswith("**")
        )
        spoken = re.sub(r"\s+", " ", spoken).strip()
        if spoken:
            yield int(m.group(1)), spoken


def duration(wav: Path) -> float:
    out = subprocess.run(
        ["ffmpeg", "-i", str(wav)], capture_output=True, text=True
    ).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def main() -> int:
    if not VOICE.exists():
        print(f"missing voice model: {VOICE}", file=sys.stderr)
        return 2
    length_scale = sys.argv[1] if len(sys.argv) > 1 else "1.0"
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0.0
    rows = []
    for no, spoken in scene_blocks(NARR.read_text(encoding="utf-8")):
        wav = OUT / f"scene-{no:02d}.wav"
        (OUT / f"scene-{no:02d}.txt").write_text(spoken, encoding="utf-8")
        subprocess.run(
            [str(PY), "-m", "piper", "-m", str(VOICE), "-f", str(wav),
             "--length-scale", length_scale, "-i", str(OUT / f"scene-{no:02d}.txt")],
            check=True, capture_output=True,
        )
        d = duration(wav)
        total += d
        rows.append((no, d, len(spoken.split())))
    for no, d, w in rows:
        print(f"scene {no:02d}: {d:6.2f}s  ({w} words)")
    print(f"TOTAL: {total:.2f}s  ({total/60:.2f} min)  length-scale={length_scale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
